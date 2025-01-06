import tempfile
from entities import config
import svgwrite
import cairosvg
from entities.editor import image_clip

def __generate_svg_cover(title:str, subtitle:str, output_path:str, config:config.CoverConfig = config.CoverConfig()):
    font_path = config.font_path
    title_font_size = config.title_font_size
    subtitle_font_size = config.subtitle_font_size
    padding = config.padding

    # Criar SVG temporário
    tmp_output_path = f'{tempfile.mktemp()}.svg'
    dwg = svgwrite.Drawing()
    
    # Calcular tamanho do texto (aproximado)
    title_width = len(title) * title_font_size * config.font_scale_rate
    subtitle_width = len(subtitle) * subtitle_font_size * config.font_scale_rate
    rect_width = max(title_width, subtitle_width) + 2 * padding
    rect_height = title_font_size + subtitle_font_size + config.line_distance + 2 * padding

    # Ajustar tamanho do desenho
    dwg['width'] = f"{rect_width}px"
    dwg['height'] = f"{rect_height}px"

    # Adicionar fundo arredondado
    dwg.add(dwg.rect(
        insert=(0, 0),
        size=(f"{rect_width}px", f"{rect_height}px"),
        fill=config.background_color,
        rx=config.rounding_radius,
        ry=config.rounding_radius
    ))

    # Centralizar título
    title_x = (rect_width - title_width) / 2 + padding
    title_y = padding + title_font_size
    dwg.add(dwg.text(
        title,
        insert=(f"{title_x}px", f"{title_y}px"),
        fill=config.title_font_color,
        font_size=f"{title_font_size}px",
        font_family=font_path
    ))

    # Centralizar subtítulo
    subtitle_x = (rect_width - subtitle_width) / 2 + padding
    subtitle_y = title_y + config.line_distance + subtitle_font_size
    dwg.add(dwg.text(
        subtitle,
        insert=(f"{subtitle_x}px", f"{subtitle_y}px"),
        fill=config.subtitle_font_color,
        font_size=f"{subtitle_font_size}px",
        font_family=font_path
    ))

    # Salvar o SVG e converter para PNG
    dwg.saveas(tmp_output_path)
    cairosvg.svg2png(url=tmp_output_path, write_to=output_path)

def generate_cover(title:str, subtitle:str, config:config.CoverConfig = config.CoverConfig()) -> image_clip.ImageClip:
    output_path = f'{tempfile.mktemp()}.png' 
    __generate_svg_cover(title, subtitle, output_path, config)
    return image_clip.ImageClip(output_path)
