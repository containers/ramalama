import re
from functools import lru_cache

from jinja2 import Environment, meta

from ramalama.model_store import go2jinja


class TemplateConversionError(Exception):
    pass


ROLE_MAP = {
    "system": "system",
    "prompt": "user",
    "user": "user",
    "response": "assistant",
    "assistant": "assistant",
}


@lru_cache(maxsize=1)
def _role_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    role_string = "|".join(map(re.escape, ROLE_MAP))
    directive = re.compile(rf"{{%\s*(if|elif)\s+({role_string})\s*%}}")
    value = re.compile(rf"{{{{\s*({role_string})\s*}}}}")
    return directive, value


def wrap_template_with_messages_loop(template: str) -> str:
    """
    Wrap a flat-variable Jinja template with OpenAI messages loop.

    Input: {% if system %}...{% endif %}{% if prompt %}...{% endif %}
    Output: {% for message in messages %}{% if message.role == 'system' %}...
        {% if message.role == 'user' %}...{% endfor %}
    """

    def directive_substitution(match: re.Match) -> str:
        directive, var = match.groups()
        return f"{{% {directive} message.role == '{ROLE_MAP[var]}' %}}"

    ROLE_DIRECTIVE_RE, ROLE_VALUE_RE = _role_patterns()

    split_point = template.rfind("<|assistant|>")
    if split_point != -1:
        last_control_end = template.rfind("%}", 0, split_point)
        if last_control_end != -1:
            split_point = last_control_end + 2
    else:
        split_point = len(template)

    wrapped = template[:split_point]
    final_assistant_output = template[split_point:]

    wrapped = ROLE_DIRECTIVE_RE.sub(directive_substitution, wrapped)
    wrapped = ROLE_VALUE_RE.sub("{{ message.content }}", wrapped)

    return f"{{% for message in messages %}}{wrapped}{{% endfor %}}{final_assistant_output}"


def get_jinja_variables(template: str) -> set[str]:
    """Returns all variables associated with a jinja template except those explicitly set in the template"""
    env = Environment()
    ast = env.parse(template)
    return meta.find_undeclared_variables(ast)


def is_openai_jinja(template: str):
    return "messages" in get_jinja_variables(template)


def ensure_jinja_openai_compatibility(template: str) -> str:
    if "messages" not in get_jinja_variables(template):
        template = wrap_template_with_messages_loop(template)

    return template


def convert_go_to_jinja(template_str: str) -> str:
    try:
        template = go2jinja.go_to_jinja(template_str)
        template = ensure_jinja_openai_compatibility(template)
    except Exception as e:
        raise TemplateConversionError from e
    return template
