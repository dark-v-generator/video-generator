"""Custom Proglog logger for MoviePy that yields ProgressEvent objects"""

import queue
from typing import (
    AsyncIterable,
    Union,
    Optional,
    Any,
    Dict,
    List,
    Callable,
    AsyncGenerator,
)
from proglog import ProgressBarLogger
import asyncio

from ..entities.progress import ProgressEvent


class AsyncProgressLogger(ProgressBarLogger):
    """
    Custom Proglog logger that captures MoviePy progress and calls a callback
    function with ProgressEvent objects.
    """

    def __init__(
        self,
        operation_name: str = "video_processing",
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        super().__init__()
        self.operation_name = operation_name
        self._progress_callback = progress_callback
        self._current_progress = 0.0
        self._current_message = ""
        self._is_finished = False
        self._error = None

    def callback(self, **changes):
        """Called by proglog when progress updates occur"""
        for parameter, value in changes.items():
            setattr(self, parameter, value)

        # Extract progress information from the changes
        progress_info = self._extract_progress_info(changes)
        if progress_info and self._progress_callback:
            event = ProgressEvent.create(
                stage="processing",
                message=progress_info["message"],
                progress=progress_info["progress"],
                details=progress_info.get("details", {}),
            )
            self._progress_callback(event)

    def bars_callback(self, bar, attr, value, old_value=None):
        """Called by proglog for progress bar updates"""
        setattr(self, attr, value)

        if not self._progress_callback:
            return

        # Handle different progress bar attributes
        if attr == "index" and hasattr(self, "total") and self.total > 0:
            progress = (value / self.total) * 100
            message = f"{self.operation_name}: {value}/{self.total}"

            event = ProgressEvent.create(
                stage="processing",
                message=message,
                progress=progress,
                details={
                    "current": value,
                    "total": self.total,
                    "operation": self.operation_name,
                },
            )
            self._progress_callback(event)
        elif attr == "message":
            # Handle message updates
            event = ProgressEvent.create(
                stage="processing",
                message=str(value),
                progress=self._current_progress,
                details={"operation": self.operation_name},
            )
            self._progress_callback(event)

    def message(self, message):
        """Called by proglog for general messages"""
        self._current_message = message
        if self._progress_callback:
            event = ProgressEvent.create(
                stage="info",
                message=str(message),
                progress=self._current_progress,
                details={"operation": self.operation_name},
            )
            self._progress_callback(event)

    def _extract_progress_info(
        self, changes: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract progress information from proglog changes"""
        progress_info = {}

        # Look for common progress indicators
        if "index" in changes and hasattr(self, "total") and self.total > 0:
            progress_info["progress"] = (changes["index"] / self.total) * 100
            progress_info["message"] = (
                f"{self.operation_name}: {changes['index']}/{self.total}"
            )
            progress_info["details"] = {
                "current": changes["index"],
                "total": self.total,
                "operation": self.operation_name,
            }
            return progress_info

        if "message" in changes:
            progress_info["progress"] = self._current_progress
            progress_info["message"] = str(changes["message"])
            progress_info["details"] = {"operation": self.operation_name}
            return progress_info

        # Look for percentage-based progress
        for key in ["progress", "percent", "percentage"]:
            if key in changes:
                progress_info["progress"] = float(changes[key])
                progress_info["message"] = (
                    f"{self.operation_name}: {progress_info['progress']:.1f}%"
                )
                progress_info["details"] = {"operation": self.operation_name}
                return progress_info

        return None

    def mark_finished(self, success: bool = True, error: Optional[Exception] = None):
        """Mark the operation as finished"""
        self._is_finished = True
        self._error = error

        if not self._progress_callback:
            return

        if success and not error:
            event = ProgressEvent.create(
                stage="completed",
                message=f"{self.operation_name} completed successfully",
                progress=100.0,
                details={"operation": self.operation_name},
            )
        else:
            event = ProgressEvent.create(
                stage="error",
                message=f"{self.operation_name} failed: {str(error) if error else 'Unknown error'}",
                details={
                    "operation": self.operation_name,
                    "error": str(error) if error else "Unknown error",
                },
            )

        self._progress_callback(event)

    def set_progress_callback(self, callback: Callable[[ProgressEvent], None]):
        """Set the progress callback function"""
        self._progress_callback = callback

    def is_finished(self) -> bool:
        """Check if the operation is finished"""
        return self._is_finished


async def create_progress_generator(
    operation_name: str, video_operation: Callable[[AsyncProgressLogger], Any]
) -> AsyncGenerator[Union[ProgressEvent, Any], None]:
    """
    Create an async generator that yields ProgressEvent objects from a video operation.

    Args:
        operation_name: Name of the operation for progress events
        video_operation: A callable that takes an AsyncProgressLogger and performs the video operation

    Yields:
        ProgressEvent objects during the operation, then the final result
    """
    events_queue = asyncio.Queue()
    operation_completed = asyncio.Event()
    operation_result = None
    operation_error = None

    def progress_callback(event: ProgressEvent):
        """Callback to handle progress events"""
        try:
            events_queue.put_nowait(event)
        except asyncio.QueueFull:
            # If queue is full, just skip this event
            pass

    # Create the logger with the callback
    logger = AsyncProgressLogger(operation_name, progress_callback)

    async def run_operation():
        """Run the video operation in a separate task"""
        nonlocal operation_result, operation_error
        try:
            operation_result = await asyncio.get_event_loop().run_in_executor(
                None, video_operation, logger
            )
            logger.mark_finished(success=True)
        except Exception as e:
            operation_error = e
            logger.mark_finished(success=False, error=e)
        finally:
            operation_completed.set()

    # Start the operation in a separate task
    operation_task = asyncio.create_task(run_operation())

    try:
        # Yield progress events as they come
        while not operation_completed.is_set() or not events_queue.empty():
            try:
                # Wait for either an event or the operation to complete
                event = await asyncio.wait_for(events_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                # No event received, continue waiting
                continue
            except Exception as e:
                # Error getting event, yield error and break
                yield ProgressEvent.create(
                    stage="error",
                    message=f"Error in progress logging: {str(e)}",
                    details={"error": str(e), "operation": operation_name},
                )
                break

        # Wait for the operation to complete
        await operation_task

        # If there was an error, raise it
        if operation_error:
            raise operation_error

        # Yield the final result if there is one
        if operation_result is not None:
            yield operation_result

    except Exception as e:
        # Cancel the operation task if it's still running
        if not operation_task.done():
            operation_task.cancel()
            try:
                await operation_task
            except asyncio.CancelledError:
                pass
        raise


class AsyncProgressLogger(ProgressBarLogger):
    """
    Asynchronous version of the progress logger for simpler use cases
    """

    def __init__(
        self,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        super().__init__()
        self.custom_stage = stage
        self.custom_message = message
        self._progress_callback = progress_callback
        self._is_finished = False
        self._queue = queue.Queue()

    def callback(self, **changes):
        """Called by proglog when progress updates occur"""
        for parameter, value in changes.items():
            setattr(self, parameter, value)

        # Extract progress information
        progress_info = self._extract_progress_info(changes)
        if progress_info:
            event = ProgressEvent.create(
                stage=self.custom_stage,
                message=self.custom_message,
                progress=progress_info["progress"],
                details=progress_info.get("details", {}),
            )
            if self._progress_callback:
                self._progress_callback(event)
            self._queue.put(event)

    def bars_callback(self, bar, attr, value, old_value=None):
        """Called by proglog for progress bar updates"""
        setattr(self, attr, value)

        if attr == "index" and hasattr(self, "total") and self.total > 0:
            progress = (value / self.total) * 100

            event = ProgressEvent.create(
                stage=self.custom_stage,
                message=self.custom_message,
                progress=progress,
                details={
                    "current": value,
                    "total": self.total,
                    "operation": self.custom_stage,
                },
            )
            if self._progress_callback:
                self._progress_callback(event)
            self._queue.put(event)

    def finish_progress(self):
        self._is_finished = True
        self._queue.put(
            ProgressEvent.create(
                stage=self.custom_stage,
                message=self.custom_message,
                progress=100.0,
                details={"operation": self.custom_stage},
            )
        )

    def is_finished(self) -> bool:
        return self._is_finished

    def put_progress_event(self, event: ProgressEvent):
        self._queue.put(event)

    async def get_progress_event(self) -> Optional[ProgressEvent]:
        while not self._is_finished:
            try:
                return self._queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.1)
        return None

    def _extract_progress_info(
        self, changes: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract progress information from proglog changes"""
        progress_info = {}

        if "index" in changes and hasattr(self, "total") and self.total > 0:
            progress_info["progress"] = (changes["index"] / self.total) * 100
            progress_info["message"] = (
                f"{self.custom_stage}: {changes['index']}/{self.total}"
            )
            progress_info["details"] = {
                "current": changes["index"],
                "total": self.total,
                "operation": self.custom_stage,
            }
            return progress_info

        if "message" in changes:
            progress_info["progress"] = None
            progress_info["message"] = str(changes["message"])
            progress_info["details"] = {"operation": self.custom_stage}
            return progress_info

        for key in ["progress", "percent", "percentage"]:
            if key in changes:
                progress_info["progress"] = float(changes[key])
                progress_info["message"] = (
                    f"{self.custom_stage}: {progress_info['progress']:.1f}%"
                )
                progress_info["details"] = {"operation": self.custom_stage}
                return progress_info

        return None
