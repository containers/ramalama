from ramalama.model_store.template_conversion import wrap_template_with_messages_loop


class TestWrapTemplateWithMessagesLoop:
    """Test suite for the wrap_template_with_messages_loop function."""

    def test_basic_system_user_assistant(self):
        """Test basic template with system, user, and assistant sections."""
        input_template = """{% if system %}<|system|>
{{ system }}<|end|>
{% endif %}{% if prompt %}<|user|>
{{ prompt }}<|end|>
{% endif %}<|assistant|>
{{ response }}<|end|>"""

        result = wrap_template_with_messages_loop(input_template)

        expected = """{% for message in messages %}{% if message.role == 'system' %}<|system|>
{{ message.content }}<|end|>
{% endif %}{% if message.role == 'user' %}<|user|>
{{ message.content }}<|end|>
{% endif %}{% endfor %}<|assistant|>
{{ response }}<|end|>"""

        assert result == expected

    def test_no_assistant_section(self):
        """Test template without assistant section falls back to wrapping everything."""
        input_template = """{% if system %}<|system|>
{{ system }}<|end|>
{% endif %}{% if prompt %}<|user|>
{{ prompt }}<|end|>
{% endif %}"""

        result = wrap_template_with_messages_loop(input_template)

        expected = """{% for message in messages %}{% if message.role == 'system' %}<|system|>
{{ message.content }}<|end|>
{% endif %}{% if message.role == 'user' %}<|user|>
{{ message.content }}<|end|>
{% endif %}{% endfor %}"""

        assert result == expected

    def test_only_assistant_section(self):
        """Test template with only assistant section."""
        input_template = """<|assistant|>
{{ response }}<|end|>"""

        result = wrap_template_with_messages_loop(input_template)

        expected = """{% for message in messages %}{% endfor %}<|assistant|>
{{ response }}<|end|>"""

        assert result == expected

    def test_multiple_assistant_sections(self):
        """Test template with multiple assistant sections - should split at the last one."""
        input_template = """{% if system %}<|system|>
{{ system }}<|end|>
{% endif %}<|assistant|>middle<|end|>{% if prompt %}<|user|>
{{ prompt }}<|end|>
{% endif %}<|assistant|>
{{ response }}<|end|>"""

        result = wrap_template_with_messages_loop(input_template)

        # Should split at the LAST <|assistant|>
        expected = """{% for message in messages %}{% if message.role == 'system' %}<|system|>
{{ message.content }}<|end|>
{% endif %}<|assistant|>middle<|end|>{% if message.role == 'user' %}<|user|>
{{ message.content }}<|end|>
{% endif %}{% endfor %}<|assistant|>
{{ response }}<|end|>"""

        assert result == expected

    def test_different_role_names(self):
        """Test with different role variable names."""
        input_template = """{% if user %}<|user|>
{{ user }}<|end|>
{% endif %}{% if assistant %}<|assistant|>
{{ assistant }}<|end|>
{% endif %}<|assistant|>
{{ response }}<|end|>"""

        result = wrap_template_with_messages_loop(input_template)

        expected = """{% for message in messages %}{% if message.role == 'user' %}<|user|>
{{ message.content }}<|end|>
{% endif %}{% if message.role == 'assistant' %}<|assistant|>
{{ message.content }}<|end|>
{% endif %}{% endfor %}<|assistant|>
{{ response }}<|end|>"""

        assert result == expected

    def test_complex_template_structure(self):
        """Test more complex template with additional formatting."""
        input_template = """{% if system %}System: {{ system }}

{% endif %}{% if prompt %}User: {{ prompt }}

{% endif %}Assistant: <|assistant|>
{{ response }}<|end|>"""

        result = wrap_template_with_messages_loop(input_template)

        expected = """{% for message in messages %}{% if message.role == 'system' %}System: {{ message.content }}

{% endif %}{% if message.role == 'user' %}User: {{ message.content }}

{% endif %}{% endfor %}Assistant: <|assistant|>
{{ response }}<|end|>"""

        assert result == expected

    def test_empty_template(self):
        """Test empty template."""
        input_template = ""
        result = wrap_template_with_messages_loop(input_template)
        expected = "{% for message in messages %}{% endfor %}"
        assert result == expected

    def test_elif_directive(self):
        """Test template with elif directive."""
        input_template = """{% if system %}<|system|>
{{ system }}<|end|>
{% elif user %}<|user|>
{{ user }}<|end|>
{% endif %}<|assistant|>
{{ response }}<|end|>"""

        result = wrap_template_with_messages_loop(input_template)

        expected = """{% for message in messages %}{% if message.role == 'system' %}<|system|>
{{ message.content }}<|end|>
{% elif message.role == 'user' %}<|user|>
{{ message.content }}<|end|>
{% endif %}{% endfor %}<|assistant|>
{{ response }}<|end|>"""

        assert result == expected

    def test_no_variables_in_assistant(self):
        """Test that assistant section doesn't get variable substitution when it has no variables."""
        input_template = """{% if system %}<|system|>
{{ system }}<|end|>
{% endif %}<|assistant|><|end|>"""

        result = wrap_template_with_messages_loop(input_template)

        expected = """{% for message in messages %}{% if message.role == 'system' %}<|system|>
{{ message.content }}<|end|>
{% endif %}{% endfor %}<|assistant|><|end|>"""

        assert result == expected

    def test_inline_template(self):
        """Test compact inline template."""
        input_template = (
            """{% if system %}<|system|>{{ system }}<|end|>{% endif %}"""
            """{% if prompt %}<|user|>{{ prompt }}<|end|>{% endif %}"""
            """<|assistant|>{{ response }}<|end|>"""
        )

        result = wrap_template_with_messages_loop(input_template)

        expected = (
            """{% for message in messages %}"""
            """{% if message.role == 'system' %}<|system|>{{ message.content }}<|end|>{% endif %}"""
            """{% if message.role == 'user' %}<|user|>{{ message.content }}<|end|>{% endif %}"""
            """{% endfor %}<|assistant|>{{ response }}<|end|>"""
        )

        assert result == expected
