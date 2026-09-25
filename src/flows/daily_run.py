"""The daily run: find the day's stories, write and render them, schedule them.

Every business decision of the run lives here, in the order it is taken: how
many stories the day gets, which errors are retried and which skip a story,
that a story's parts render all or nothing, which slot each video takes. The
capabilities do the work, the store keeps the record, and the caller (the bot,
the command line) only decides where the progress lines go.
"""

import asyncio
import dataclasses
from dataclasses import dataclass
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ..capabilities.discovery import StoryDiscovery
from ..capabilities.publishing import HashtagSuggester, ITikTokPublisherProxy
from ..capabilities.rendering import Renderer
from ..capabilities.writing import (
    StoryWriter,
    WriterContentBlockedError,
    WriterTransientError,
)
from ..entities.configs.flows import DailyRunConfig
from ..entities.generated_video import GeneratedVideo
from ..entities.story import Story
from ..entities.story_candidate import EvaluatedStory
from ..storage import PublishLogEntry, RunStore
from .progress import Progress, short_error
from .publish_slots import next_publish_slot

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = "output/daily"


@dataclass(kw_only=True)
class DailyRun:
    discovery: StoryDiscovery
    writer: StoryWriter
    renderer: Renderer
    # None only for a run that never publishes (generate-only).
    publisher: Optional[ITikTokPublisherProxy]
    hashtags: HashtagSuggester
    store: RunStore
    config: DailyRunConfig
    progress: Progress
    now: Callable[[], datetime] = datetime.now

    async def generate(
        self, *, count: Optional[int] = None, output_dir: str = DEFAULT_OUTPUT_DIR
    ) -> list[GeneratedVideo]:
        """Write and render the day's stories without publishing them."""
        candidates, target = await self._find(count, output_dir, publishing=False)
        if not target:
            return []

        generated: list[GeneratedVideo] = []
        done = 0
        for number, candidate in enumerate(candidates, start=1):
            if done >= target:
                break
            produced = await self._produce(candidate, number, target, output_dir)
            if produced is None:
                continue
            await self.progress(f"#{number} Vídeo finalizado.")
            generated.extend(produced[1])
            done += 1

        await self.progress(f"✅ Geração finalizada: {done}/{target} vídeos prontos.")
        return generated

    async def run(
        self, *, count: Optional[int] = None, output_dir: str = DEFAULT_OUTPUT_DIR
    ) -> None:
        """Write, render and schedule stories until the day's target is published."""
        candidates, target = await self._find(count, output_dir, publishing=True)
        if not target:
            return

        # Part k goes in the slot after part k-1; the next story starts after
        # the last slot that was actually taken.
        last_slot = self.now()
        published = 0
        for number, candidate in enumerate(candidates, start=1):
            if published >= target:
                break
            produced = await self._produce(candidate, number, target, output_dir)
            if produced is None:
                continue
            story, videos = produced
            await self.progress(f"#{number} Vídeo finalizado. Agendando história...")
            hashtags: list[str] = []  # asked for once, shared by every part
            try:
                for video in videos:
                    last_slot = await self._schedule(video, last_slot, hashtags, story)
                    await self.progress(
                        f"#{number} Agendamento concluído para "
                        f"{last_slot.strftime('%d/%m %H:%M')}"
                    )
            except Exception as e:
                await self.progress(
                    f"❌ #{number} Erro ao publicar: {short_error(e)}. "
                    "Pulando para uma nova história."
                )
                continue
            published += 1

        await self.progress(
            f"✅ Fluxo finalizado: {published}/{target} vídeos agendados."
        )

    async def publish(self, videos: list[GeneratedVideo]) -> None:
        """Schedule videos generated earlier, in order; a failure skips only that one."""
        if not videos:
            await self.progress("Nenhum vídeo para publicar.")
            return
        await self.progress(f"📤 Agendando {len(videos)} vídeos...")

        last_slot = self.now()
        for number, video in enumerate(videos, start=1):
            try:
                last_slot = await self._schedule(video, last_slot, [])
            except Exception as e:
                await self.progress(
                    f"❌ [#{number} — {video.title[:60]}] Erro: {short_error(e)}"
                )
                continue
            await self.progress(
                f"#{number} Agendamento concluído para "
                f"{last_slot.strftime('%d/%m %H:%M')}"
            )

        await self.progress("🏁 Agendamento concluído.")

    async def _find(
        self, count: Optional[int], output_dir: str, *, publishing: bool
    ) -> tuple[list[EvaluatedStory], int]:
        """Every candidate not yet scheduled (spares replace skipped stories)
        and how many stories the day gets."""
        await self.progress("🔄 Busca diária iniciada...")
        requested = count if count is not None else self.config.count
        try:
            candidates = await self.discovery.find_best_stories(
                language=self.config.language,
                sort="top",
                time_filter="day",
                top_per_sub=5,
                exclude_urls=self.store.scheduled_post_urls(),
            )
        except Exception as e:
            logger.exception("Failed to find stories")
            await self.progress(f"Erro ao buscar histórias: {e}")
            return [], 0
        if not candidates:
            await self.progress("Nenhuma história boa encontrada hoje.")
            return [], 0

        target = min(requested, len(candidates))
        if target:
            plan = (
                "Iniciando geração de vídeo e agendamento."
                if publishing
                else f"Iniciando geração de {target} vídeo{'s' if target != 1 else ''}."
            )
            await self.progress(
                f"✅ Busca finalizada: {len(candidates)} histórias disponíveis. {plan}"
            )
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        return candidates, target

    async def _produce(
        self, candidate: EvaluatedStory, number: int, target: int, output_dir: str
    ) -> Optional[tuple[Story, list[GeneratedVideo]]]:
        """Write and render one candidate; None when it has to be skipped."""
        story = await self._write(candidate, number, target)
        if story is None:
            return None

        try:
            rendered = await self.renderer.render(
                story, low_quality=self.config.low_quality
            )
        except Exception as e:
            logger.exception("Failed to generate video for %s", story.origin.url)
            await self.progress(
                f"❌ #{number} Erro na geração de vídeo: {short_error(e)}. "
                "Pulando para a próxima história."
            )
            return None

        # Only reached once every part rendered: a story is all or nothing.
        videos = []
        for part in rendered:
            index = part.part.index
            suffix = f"_p{index}" if index > 1 else ""
            video_path = Path(output_dir) / f"story_{number:02d}{suffix}.mp4"
            video_path.write_bytes(part.video)
            video = GeneratedVideo(
                video_path=str(video_path),
                title=story.cover_title_for(part.part),
                summary=story.summary,
                post_url=story.origin.url,
                part=index if story.is_multipart else None,
            )
            self.store.save_manifest(video, output_dir)
            videos.append(video)
            if story.is_multipart:
                await self.progress(f"#{number} Parte {index} gerada")
        return story, videos

    async def _write(
        self, candidate: EvaluatedStory, number: int, target: int
    ) -> Optional[Story]:
        """The candidate's script, retrying passing errors; None skips it."""
        post = candidate.post
        retries = self.config.story_retry_max
        await self.progress(f'🎬 Gerando história #{number}: "{post.title}"')

        for attempt in range(1, retries + 1):
            try:
                suffix = f" (tentativa {attempt}/{retries})" if attempt > 1 else ""
                await self.progress(f"#{number} Gerando roteiro...{suffix}")
                origin = self.discovery.fetch(post.url)
                story = await self.writer.write(origin, language=self.config.language)
                await self.progress(f"#{number} Roteiro finalizado. Gerando vídeo...")
                return dataclasses.replace(story, summary=candidate.resumo[:400])

            except WriterContentBlockedError as e:
                logger.warning("Content filter on %s, skipping: %s", post.url, e)
                await self.progress(
                    f"⚠️ #{number} Bloqueado por filtro de conteúdo, pulando."
                )
                return None

            except Exception as e:
                if isinstance(e, WriterTransientError) and attempt < retries:
                    delay = self.config.story_retry_base_delay * (2 ** (attempt - 1))
                    logger.warning("Transient error on %s: %s", post.url, e)
                    await self.progress(
                        f"⏳ #{number} Erro temporário, tentando de novo em {delay}s "
                        f"(tentativa {attempt}/{retries})..."
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.exception("Failed to prepare story for %s", post.url)
                await self.progress(
                    f"❌ #{number} Erro no roteiro: {short_error(e)}. "
                    f"Tentando outra história para completar {target}."
                )
                return None
        return None

    async def _schedule(
        self,
        video: GeneratedVideo,
        after: datetime,
        tags: list[str],
        story: Optional[Story] = None,
    ) -> datetime:
        """Publish *video* in the first slot after *after* and log the outcome.

        Returns the slot taken, raises on failure. An empty *tags* is filled from
        the story (or the video, without one) and then reused by the caller.
        """
        slot: Optional[datetime] = None
        try:
            slot = next_publish_slot(
                after=after,
                slot_times=self.config.publish_slots_local,
                min_lead_minutes=self.config.publish_min_lead_minutes,
                _now=self.now(),
            )
            if not tags and story and story.hashtags:
                tags.extend(self.hashtags.normalize(story.hashtags))
            elif not tags:
                about = story or video
                tags.extend(await self.hashtags.suggest(about.title, about.summary))
            result = await self.publisher.publish_video(
                video_path=video.video_path,
                description=video.title,
                hashtags=tags,
                schedule_at=slot,
            )
        except Exception as e:
            logger.exception("Failed to publish %s", video.video_path)
            self.store.append_publish_log(
                PublishLogEntry("failed", slot, video, list(tags), error=short_error(e))
            )
            raise
        self.store.append_publish_log(
            PublishLogEntry("scheduled", slot, video, list(tags), publish_result=result)
        )
        return slot
