from functools import singledispatchmethod

from jinja2 import Environment, meta

from ramalama.model_store import go2jinja


class TemplateConversionError(Exception):
    pass


class TemplateIdentificationError(Exception):
    pass


def wrap_template_with_messages_loop(jinja_template: str) -> str:
    """
    Wrap a flat-variable Jinja template with OpenAI messages loop.

    Input: {% if system %}...{% endif %}{% if prompt %}...{% endif %}
    Output: {% for message in messages %}{% if message.role == 'system' %}...
        {% if message.role == 'user' %}...{% endfor %}
    """
    # First, pull out the final assistant chunk if present
    split_point = jinja_template.rfind('<|assistant|>')
    if split_point == -1:
        split_point = len(jinja_template)
    else:
        last_control_end = jinja_template.rfind('%}', 0, split_point)
        if last_control_end != -1:
            split_point = last_control_end + 2

    wrapped = jinja_template[:split_point]
    final_assistant_output = jinja_template[split_point:]

    role_map = {"system": "system", "prompt": "user", "user": "user", "response": "assistant", "assistant": "assistant"}
    control_directives = ['if', 'elif']

    # Substitute for control directives and role labels
    for role, new_role in role_map.items():
        for directive in control_directives:
            wrapped = wrapped.replace(
                f"{{% {directive} {role} %}}", f"{{% {directive} message.role == '{new_role}' %}}"
            )
        wrapped = wrapped.replace(f"{{{{ {role} }}}}", "{{ message.content }}")

    # recombine wrapped template
    return f"{{% for message in messages %}}{wrapped}{{% endfor %}}{final_assistant_output}"


def get_jinja_variables(template: str) -> set[str]:
    """Returns all variables associated with a jinja template except those explicitly set in the template"""
    env = Environment()
    ast = env.parse(template)
    return meta.find_undeclared_variables(ast)


class BaseStyle:
    pass


class OpenAIStyle(BaseStyle):
    pass


class OllamaStyle(BaseStyle):
    pass


class Styles:
    openai = OpenAIStyle()
    ollama = OllamaStyle()


class TemplateStyle:
    style: BaseStyle = BaseStyle()

    def __init__(self, template: str):
        self.template = template

    def convert(self, target_style: BaseStyle) -> str:
        raise Exception(
            f"No supported conversion method {self.__class__.__name__} and {target_style.__class__.__name__} templates"
        )


class OpenAITemplateStyle(TemplateStyle):
    style = OpenAIStyle()

    @singledispatchmethod
    def convert(self, target_style: BaseStyle):
        super().convert(target_style)

    @convert.register
    def _(self, target_style: OpenAIStyle) -> str:
        return self.template


class OllamaTemplateStyle(TemplateStyle):
    style = OllamaStyle()

    @singledispatchmethod
    def convert(self, target_style: BaseStyle):
        super().convert(target_style)

    @convert.register
    def _(self, target_style: OpenAIStyle) -> str:
        template = go2jinja.go_to_jinja(self.template)
        if "messages" not in get_jinja_variables(template):
            template = wrap_template_with_messages_loop(template)
        return template


def identify_template_style(template_str: str) -> TemplateStyle:
    try:
        if go2jinja.is_go_template(template_str):
            return OllamaTemplateStyle(template_str)
        else:
            return OpenAITemplateStyle(template_str)
    except Exception as e:
        raise TemplateIdentificationError("template identication failed") from e


def convert_template(template_str: str, target_style: BaseStyle) -> str:
    template_style = identify_template_style(template_str)
    try:
        return template_style.convert(target_style)
    except Exception as e:
        raise TemplateConversionError("template conversion failed") from e


class StyleHandler:
    def __init__(self, target_template_style: OpenAITemplateStyle):
        self.target_template_style = target_template_style

    def get_template_style(self, template: str) -> TemplateStyle:
        return identify_template_style(template)

    def needs_conversion(self, template_style: TemplateStyle) -> bool:
        return isinstance(template_style, self.target_template_style)

    def convert_template(self, template_style: TemplateStyle) -> str:
        return template_style.convert(self.target_style)


DEFAULT_STYLE_HANDLER = StyleHandler(target_template_style=OpenAITemplateStyle)
