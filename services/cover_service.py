import tempfile
import svgwrite
import cairosvg
from entities.editor import image_clip

def __generate_svg_cover(title, subtitle, output_path="cover.png"):
    font_path = "assets/kite_one.ttf"  # Substitua pelo caminho da sua fonte personalizada
    title_font_size = 80
    subtitle_font_size = 50
    padding = 50

    # Criar SVG temporário
    tmp_output_path = f'{tempfile.mktemp()}.svg'
    dwg = svgwrite.Drawing()
    
    # Calcular tamanho do texto (aproximado)
    title_width = len(title) * title_font_size * 0.6  # Aproximação de largura do texto
    subtitle_width = len(subtitle) * subtitle_font_size * 0.6
    rect_width = max(title_width, subtitle_width) + 2 * padding
    rect_height = title_font_size + subtitle_font_size + 3 * padding

    # Ajustar tamanho do desenho
    dwg['width'] = f"{rect_width}px"
    dwg['height'] = f"{rect_height}px"

    # Adicionar fundo arredondado
    dwg.add(dwg.rect(
        insert=(0, 0),
        size=(f"{rect_width}px", f"{rect_height}px"),
        fill="white",
        rx=30, ry=30
    ))

    # Centralizar título
    title_x = (rect_width - title_width) / 2
    title_y = padding + title_font_size
    dwg.add(dwg.text(
        title,
        insert=(f"{title_x}px", f"{title_y}px"),
        fill="black",
        font_size=f"{title_font_size}px",
        font_family=font_path
    ))

    # Centralizar subtítulo
    subtitle_x = (rect_width - subtitle_width) / 2
    subtitle_y = title_y + padding + subtitle_font_size
    dwg.add(dwg.text(
        subtitle,
        insert=(f"{subtitle_x}px", f"{subtitle_y}px"),
        fill="gray",
        font_size=f"{subtitle_font_size}px",
        font_family=font_path
    ))

    # Salvar o SVG e converter para PNG
    dwg.saveas(tmp_output_path)
    cairosvg.svg2png(url=tmp_output_path, write_to=output_path)

def generate_cover(title, subtitle="") -> image_clip.ImageClip:
    output_path = f'{tempfile.mktemp()}.png' 
    __generate_svg_cover(title, subtitle, output_path)
    return image_clip.ImageClip(output_path)
