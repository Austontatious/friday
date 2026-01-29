import os
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def load_template(template_name: str):
    return env.get_template(template_name)

def render_template(template_name: str, context: dict) -> str:
    """Render template with context and sanitize output."""
    template = load_template(template_name)
    rendered = template.render(context)
    # Strip BOM and leading/trailing whitespace
    return rendered.replace('\ufeff', '').strip()

