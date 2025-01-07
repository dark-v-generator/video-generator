import tempfile
from entities import config
import svgwrite
import cairosvg
from entities.editor import image_clip

def __generate_svg_cover(title:str, subtitle:str, output_path:str, config:config.CoverConfig = config.CoverConfig()):
    # Criar SVG temporário
    tmp_output_path = f'{tempfile.mktemp()}.svg'
    dwg = svgwrite.Drawing()

    # Ajustar tamanho do desenho
    dwg['width'] = f"{config.width}px"
    dwg['height'] = f"{config.height}px"

    # Adicionar fundo arredondado
    dwg.add(dwg.rect(
        insert=(0, 0),
        size=(f"{config.width}px", f"{config.height}px"),
        fill=config.background_color,
        rx=config.rounding_radius,
        ry=config.rounding_radius
    ))

    dwg.add(dwg.text(
        title,
        insert=("50%", "50%"),
        fill=config.title_font_color,
        font_size=f"{config.title_font_size}px",
        font_family=config.font_path,
        text_anchor="middle"
    ))

    dwg.add(dwg.text(
        subtitle,
        insert=("50%", "80%"),
        fill=config.subtitle_font_color,
        font_size=f"{config.subtitle_font_size}px",
        font_family=config.font_path,
        text_anchor="middle"
    ))

    # Salvar o SVG e converter para PNG
    dwg.saveas(tmp_output_path)
    cairosvg.svg2png(url=tmp_output_path, write_to=output_path)

def generate_cover(title:str, subtitle:str, config:config.CoverConfig = config.CoverConfig()) -> image_clip.ImageClip:
    output_path = f'{tempfile.mktemp()}.png'
    __generate_svg_cover(title, subtitle, output_path, config)
    print(f'Cover generated at {output_path}')
    return image_clip.ImageClip(output_path)
