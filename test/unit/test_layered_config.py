from dataclasses import dataclass, field
from typing import Any, Dict, List

from ramalama.layered_config import LayeredMixin, build_subconfigs, deep_merge, extract_defaults


@dataclass
class SimpleConfig:
    name: str
    value: int


@dataclass
class NestedConfig:
    title: str
    count: int
    simple: SimpleConfig


@dataclass
class ComplexConfig:
    simple: SimpleConfig
    nested: NestedConfig
    direct_value: str


@dataclass
class MixedConfig:
    simple: SimpleConfig
    complex: ComplexConfig
    regular_dict: Dict[str, Any]
    regular_list: List[str]
    string_value: str
    int_value: int


def default_simple_config() -> SimpleConfig:
    return SimpleConfig(name="default_simple", value=42)


def default_nested_config() -> NestedConfig:
    return NestedConfig(title="default_title", count=100, simple=default_simple_config())


def default_complex_config() -> ComplexConfig:
    return ComplexConfig(simple=default_simple_config(), nested=default_nested_config(), direct_value="default_direct")


@dataclass
class MixedConfigWithDefaults:
    regular_dict: Dict[str, Any]
    regular_list: List[str]
    simple: SimpleConfig = field(default_factory=default_simple_config)
    complex: ComplexConfig = field(default_factory=default_complex_config)
    string_value: str = "default_string"
    int_value: int = 999


class TestExtractDefaults:
    """Test the extract_defaults function."""

    def test_extract_defaults_without_defaults(self):
        """Test extracting defaults from a dataclass without default values."""
        defaults = extract_defaults(SimpleConfig)
        assert defaults == {}

    def test_extract_defaults_mixed_config(self):
        """Test extracting defaults from a mixed config with defaults."""
        defaults = extract_defaults(MixedConfigWithDefaults)
        expected = {
            "simple": SimpleConfig(name="default_simple", value=42),
            "complex": ComplexConfig(
                simple=SimpleConfig(name="default_simple", value=42),
                nested=NestedConfig(
                    title="default_title", count=100, simple=SimpleConfig(name="default_simple", value=42)
                ),
                direct_value="default_direct",
            ),
            "string_value": "default_string",
            "int_value": 999,
        }
        assert defaults == expected


class TestBuildSubconfigs:
    """Test the build_subconfigs function."""

    def test_build_subconfigs_simple_nested(self):
        """Test building subconfigs with simple nested dataclasses."""
        values = {
            "simple": {"name": "test", "value": 123},
            "nested": {"title": "nested_test", "count": 456, "simple": {"name": "nested_simple", "value": 789}},
            "direct_value": "direct_value",
        }

        result = build_subconfigs(values, ComplexConfig)

        assert isinstance(result["simple"], SimpleConfig)
        assert result["simple"].name == "test"
        assert result["simple"].value == 123

        assert isinstance(result["nested"], NestedConfig)
        assert result["nested"].title == "nested_test"
        assert result["nested"].count == 456
        assert isinstance(result["nested"].simple, SimpleConfig)
        assert result["nested"].simple.name == "nested_simple"
        assert result["nested"].simple.value == 789

        assert result["direct_value"] == "direct_value"

    def test_build_subconfigs_mixed_types(self):
        """Test building subconfigs with mixed dataclass and non-dataclass types."""
        values = {
            "simple": {"name": "test", "value": 123},
            "complex": {
                "simple": {"name": "complex_simple", "value": 456},
                "nested": {
                    "title": "complex_nested",
                    "count": 789,
                    "simple": {"name": "complex_nested_simple", "value": 101},
                },
                "direct_value": "complex_direct",
            },
            "regular_dict": {"key": "value", "number": 42},
            "regular_list": ["item1", "item2", "item3"],
            "string_value": "just_a_string",
            "int_value": 999,
        }

        result = build_subconfigs(values, MixedConfig)

        assert isinstance(result["simple"], SimpleConfig)
        assert result["simple"].name == "test"
        assert result["simple"].value == 123

        assert isinstance(result["complex"], ComplexConfig)
        assert isinstance(result["complex"].simple, SimpleConfig)
        assert isinstance(result["complex"].nested, NestedConfig)
        assert isinstance(result["complex"].nested.simple, SimpleConfig)
        assert result["complex"].simple.name == "complex_simple"
        assert result["complex"].nested.title == "complex_nested"
        assert result["complex"].nested.simple.name == "complex_nested_simple"
        assert result["complex"].direct_value == "complex_direct"

        assert result["regular_dict"] == {"key": "value", "number": 42}
        assert result["regular_list"] == ["item1", "item2", "item3"]
        assert result["string_value"] == "just_a_string"
        assert result["int_value"] == 999

    def test_build_subconfigs_no_nested_dataclasses(self):
        """Test building subconfigs when no nested dataclasses are present."""
        values = {"name": "test", "value": 123}

        result = build_subconfigs(values, SimpleConfig)

        assert result == values

    def test_build_subconfigs_empty_dict(self):
        """Test building subconfigs with an empty dictionary."""
        values = {}

        result = build_subconfigs(values, SimpleConfig)

        assert result == {}

    def test_build_subconfigs_nonexistent_annotation(self):
        """Test building subconfigs with a key that doesn't exist in annotations."""
        values = {"nonexistent_key": {"some": "data"}}

        result = build_subconfigs(values, SimpleConfig)

        assert result == values

    def test_build_subconfigs_non_dict_value(self):
        """Test building subconfigs when a value is not a dict."""
        values = {"simple": "not_a_dict"}

        result = build_subconfigs(values, SimpleConfig)

        assert result == values

    def test_build_subconfigs_non_dataclass_type(self):
        """Test building subconfigs when the annotation type is not a dataclass."""

        @dataclass
        class ConfigWithNonDataclass:
            simple: SimpleConfig
            regular_list: list
            regular_dict: dict

        values = {
            "simple": {"name": "test", "value": 123},
            "regular_list": ["items", "in", "list"],
            "regular_dict": {"key": "value"},
        }

        result = build_subconfigs(values, ConfigWithNonDataclass)

        assert isinstance(result["simple"], SimpleConfig)
        assert result["regular_list"] == ["items", "in", "list"]
        assert result["regular_dict"] == {"key": "value"}

    def test_build_subconfigs_deep_nesting(self):
        """Test building subconfigs with deep nesting."""

        @dataclass
        class DeepNestedConfig:
            level1: ComplexConfig

        values = {
            "level1": {
                "simple": {"name": "deep", "value": 1},
                "nested": {"title": "deep_nested", "count": 2, "simple": {"name": "deep_nested_simple", "value": 3}},
                "direct_value": "deep_value",
            }
        }

        result = build_subconfigs(values, DeepNestedConfig)

        assert isinstance(result["level1"], ComplexConfig)
        assert isinstance(result["level1"].simple, SimpleConfig)
        assert isinstance(result["level1"].nested, NestedConfig)
        assert isinstance(result["level1"].nested.simple, SimpleConfig)
        assert result["level1"].simple.name == "deep"
        assert result["level1"].nested.title == "deep_nested"
        assert result["level1"].nested.simple.name == "deep_nested_simple"
        assert result["level1"].direct_value == "deep_value"

    def test_build_subconfigs_preserves_original_dict(self):
        """Test that build_subconfigs doesn't modify the original dictionary."""

        @dataclass
        class SimpleNestedConfig:
            simple: SimpleConfig

        original_values = {"simple": {"name": "test", "value": 123}}
        values_copy = original_values.copy()

        result = build_subconfigs(values_copy, SimpleNestedConfig)

        assert original_values == {"simple": {"name": "test", "value": 123}}
        assert isinstance(result["simple"], SimpleConfig)

    def test_build_subconfigs_multiple_nested_dataclasses(self):
        """Test building subconfigs with multiple nested dataclasses."""

        @dataclass
        class MultiNestedConfig:
            config1: SimpleConfig
            config2: NestedConfig
            config3: SimpleConfig

        values = {
            "config1": {"name": "first", "value": 1},
            "config2": {"title": "second", "count": 2, "simple": {"name": "second_simple", "value": 22}},
            "config3": {"name": "third", "value": 3},
        }

        result = build_subconfigs(values, MultiNestedConfig)

        assert isinstance(result["config1"], SimpleConfig)
        assert isinstance(result["config2"], NestedConfig)
        assert isinstance(result["config3"], SimpleConfig)

        assert result["config1"].name == "first"
        assert result["config2"].title == "second"
        assert result["config2"].simple.name == "second_simple"
        assert result["config3"].name == "third"

    def test_build_subconfigs_with_nested_defaults(self):
        """Test building subconfigs with nested dataclasses that have defaults."""
        values = {"title": "custom_title", "count": 200, "simple": {"name": "custom_simple", "value": 300}}

        result = build_subconfigs(values, NestedConfig)

        assert isinstance(result["simple"], SimpleConfig)
        assert result["simple"].name == "custom_simple"
        assert result["simple"].value == 300

        assert result["title"] == "custom_title"
        assert result["count"] == 200

    def test_build_subconfigs_with_complex_defaults(self):
        """Test building subconfigs with complex nested dataclasses that have defaults."""
        values = {
            "simple": {"name": "complex_simple", "value": 400},
            "nested": {
                "title": "complex_nested_title",
                "count": 500,
                "simple": {"name": "complex_nested_simple", "value": 600},
            },
            "direct_value": "custom_direct",
        }

        result = build_subconfigs(values, ComplexConfig)

        assert isinstance(result["simple"], SimpleConfig)
        assert result["simple"].name == "complex_simple"
        assert result["simple"].value == 400

        assert isinstance(result["nested"], NestedConfig)
        assert result["nested"].title == "complex_nested_title"
        assert result["nested"].count == 500
        assert isinstance(result["nested"].simple, SimpleConfig)
        assert result["nested"].simple.name == "complex_nested_simple"
        assert result["nested"].simple.value == 600

        assert result["direct_value"] == "custom_direct"

    def test_build_subconfigs_with_mixed_defaults(self):
        """Test building subconfigs with mixed nested dataclasses that have defaults."""
        values = {
            "simple": {"name": "mixed_simple", "value": 700},
            "complex": {
                "simple": {"name": "mixed_complex_simple", "value": 800},
                "nested": {
                    "title": "mixed_complex_nested",
                    "count": 900,
                    "simple": {"name": "mixed_complex_nested_simple", "value": 1000},
                },
                "direct_value": "mixed_complex_direct",
            },
            "string_value": "custom_string",
            "int_value": 1100,
        }

        result = build_subconfigs(values, MixedConfigWithDefaults)

        assert isinstance(result["simple"], SimpleConfig)
        assert result["simple"].name == "mixed_simple"
        assert result["simple"].value == 700

        assert isinstance(result["complex"], ComplexConfig)
        assert isinstance(result["complex"].simple, SimpleConfig)
        assert result["complex"].simple.name == "mixed_complex_simple"
        assert result["complex"].simple.value == 800

        assert isinstance(result["complex"].nested, NestedConfig)
        assert result["complex"].nested.title == "mixed_complex_nested"
        assert result["complex"].nested.count == 900
        assert isinstance(result["complex"].nested.simple, SimpleConfig)
        assert result["complex"].nested.simple.name == "mixed_complex_nested_simple"
        assert result["complex"].nested.simple.value == 1000

        assert result["complex"].direct_value == "mixed_complex_direct"
        assert result["string_value"] == "custom_string"
        assert result["int_value"] == 1100

    def test_build_subconfigs_partial_nested_defaults(self):
        """Test building subconfigs with partial data for nested dataclasses with defaults."""
        values = {
            "title": "partial_title",
        }

        result = build_subconfigs(values, NestedConfig)

        assert result["title"] == "partial_title"

        assert "count" not in result
        assert "simple" not in result

    def test_build_subconfigs_deep_nesting_with_defaults(self):
        """Test building subconfigs with deep nesting and defaults at multiple levels."""
        values = {
            "simple": {"name": "deep_simple", "value": 1200},
            "complex": {
                "simple": {"name": "deep_complex_simple", "value": 1300},
                "nested": {
                    "title": "deep_complex_nested",
                    "count": 1400,
                    "simple": {"name": "deep_complex_nested_simple", "value": 1500},
                },
                "direct_value": "deep_complex_direct",
            },
        }

        result = build_subconfigs(values, MixedConfigWithDefaults)

        assert isinstance(result["simple"], SimpleConfig)
        assert result["simple"].name == "deep_simple"

        assert isinstance(result["complex"], ComplexConfig)
        assert isinstance(result["complex"].simple, SimpleConfig)
        assert result["complex"].simple.name == "deep_complex_simple"

        assert isinstance(result["complex"].nested, NestedConfig)
        assert result["complex"].nested.title == "deep_complex_nested"
        assert isinstance(result["complex"].nested.simple, SimpleConfig)
        assert result["complex"].nested.simple.name == "deep_complex_nested_simple"


class TestDeepMerge:
    """Test the deep_merge function."""

    def test_deep_merge_simple_dicts(self):
        """Test merging simple dictionaries."""
        left = {"a": 1, "b": 2}
        right = {"b": 3, "c": 4}

        result = deep_merge(left, right)

        assert result == {"a": 1, "b": 3, "c": 4}
        assert left == {"a": 1, "b": 3, "c": 4}  # left is modified in place

    def test_deep_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        left = {"a": {"x": 1, "y": 2}, "b": 3}
        right = {"a": {"y": 4, "z": 5}, "c": 6}

        result = deep_merge(left, right)

        expected = {"a": {"x": 1, "y": 4, "z": 5}, "b": 3, "c": 6}
        assert result == expected
        assert left == expected

    def test_deep_merge_deeply_nested_dicts(self):
        """Test merging deeply nested dictionaries."""
        left = {"level1": {"level2": {"level3": {"value": "original", "keep": True}}, "other": "unchanged"}}
        right = {"level1": {"level2": {"level3": {"value": "updated", "new": "added"}}}}

        result = deep_merge(left, right)

        expected = {
            "level1": {"level2": {"level3": {"value": "updated", "keep": True, "new": "added"}}, "other": "unchanged"}
        }
        assert result == expected
        assert left == expected

    def test_deep_merge_overwrite_non_dict(self):
        """Test that non-dict values are overwritten."""
        left = {"a": {"b": 1}, "c": "string", "d": [1, 2, 3]}
        right = {"a": "overwritten", "c": {"nested": "dict"}, "d": "also_overwritten"}

        result = deep_merge(left, right)

        expected = {"a": "overwritten", "c": {"nested": "dict"}, "d": "also_overwritten"}
        assert result == expected
        assert left == expected

    def test_deep_merge_empty_dicts(self):
        """Test merging with empty dictionaries."""
        left = {"a": 1, "b": {"c": 2}}
        right = {}

        result = deep_merge(left, right)

        assert result == {"a": 1, "b": {"c": 2}}
        assert left == {"a": 1, "b": {"c": 2}}

    def test_deep_merge_empty_left(self):
        """Test merging when left dict is empty."""
        left = {}
        right = {"a": 1, "b": {"c": 2}}

        result = deep_merge(left, right)

        assert result == {"a": 1, "b": {"c": 2}}
        assert left == {"a": 1, "b": {"c": 2}}

    def test_deep_merge_both_empty(self):
        """Test merging two empty dictionaries."""
        left = {}
        right = {}

        result = deep_merge(left, right)

        assert result == {}
        assert left == {}

    def test_deep_merge_multiple_layers(self):
        """Test merging with multiple nested layers."""
        left = {
            "config": {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "credentials": {"username": "user", "password": "pass"},
                },
                "logging": {"level": "info"},
            }
        }
        right = {
            "config": {
                "database": {"port": 5433, "credentials": {"password": "newpass"}},
                "logging": {"level": "debug", "file": "/var/log/app.log"},
            }
        }

        result = deep_merge(left, right)

        expected = {
            "config": {
                "database": {
                    "host": "localhost",
                    "port": 5433,
                    "credentials": {"username": "user", "password": "newpass"},
                },
                "logging": {"level": "debug", "file": "/var/log/app.log"},
            }
        }
        assert result == expected
        assert left == expected

    def test_deep_merge_preserves_original_right(self):
        """Test that the right dictionary is not modified."""
        left = {"a": 1}
        right = {"b": 2, "c": {"d": 3}}
        right_copy = right.copy()

        deep_merge(left, right)

        assert right == right_copy  # right should be unchanged

    def test_deep_merge_with_none_values(self):
        """Test merging with None values."""
        left = {"a": 1, "b": {"c": 2}}
        right = {"a": None, "b": {"c": None, "d": 3}}

        result = deep_merge(left, right)

        expected = {"a": None, "b": {"c": None, "d": 3}}
        assert result == expected
        assert left == expected

    def test_deep_merge_with_false_values(self):
        """Test merging with False values."""
        left = {"a": True, "b": {"c": True}}
        right = {"a": False, "b": {"c": False, "d": True}}

        result = deep_merge(left, right)

        expected = {"a": False, "b": {"c": False, "d": True}}
        assert result == expected
        assert left == expected

    def test_deep_merge_with_zero_values(self):
        """Test merging with zero values."""
        left = {"a": 1, "b": {"c": 1}}
        right = {"a": 0, "b": {"c": 0, "d": 1}}

        result = deep_merge(left, right)

        expected = {"a": 0, "b": {"c": 0, "d": 1}}
        assert result == expected
        assert left == expected


class TestLayeredMixin:
    """Test the LayeredMixin class integration with deep merge."""

    @dataclass
    class ConfigTest:
        name: str = "default"
        value: int = 42
        nested: dict = field(default_factory=lambda: {"key": "default"})
        settings: dict = field(default_factory=lambda: {"enabled": False})

    class LayeredTestConfig(LayeredMixin, ConfigTest):
        pass

    def test_layered_mixin_simple_override(self):
        """Test simple value override in layered config."""
        layer1 = {"name": "layer1", "value": 100}
        layer2 = {"name": "layer2"}

        config = self.LayeredTestConfig(layer1, layer2)

        assert config.name == "layer1"
        assert config.value == 100  # from layer1
        assert config.is_set("name") is True
        assert config.is_set("value") is True

    def test_layered_mixin_defaults_preserved(self):
        """Test that defaults are preserved when not overridden."""
        layer1 = {"name": "custom_name"}

        config = self.LayeredTestConfig(layer1)

        assert config.name == "custom_name"
        assert config.value == 42  # default preserved
        assert config.nested == {"key": "default"}  # default preserved
        assert config.settings == {"enabled": False}  # default preserved

    def test_layered_mixin_is_set_tracking(self):
        """Test that is_set correctly tracks which layers set values."""
        layer1 = {"name": "layer1"}
        layer2 = {"value": 100}

        config = self.LayeredTestConfig(layer1, layer2)

        assert config.is_set("name") is True
        assert config.is_set("value") is True
        assert config.is_set("nested") is False
        assert config.is_set("settings") is False

    def test_layered_mixin_empty_layers(self):
        """Test behaviour with empty layers."""
        layer1 = {}
        layer2 = {"name": "layer2"}
        layer3 = {}

        config = self.LayeredTestConfig(layer1, layer2, layer3)

        assert config.name == "layer2"
        assert config.value == 42  # default
        assert config.is_set("name") is True
        assert config.is_set("value") is False

    def test_layered_mixin_complex_nesting(self):
        """Test complex nested structures in layered config."""
        layer1 = {
            "settings": {
                "database": {"host": "localhost", "port": 5432},
            }
        }
        layer2 = {
            "settings": {
                "database": {"port": 5433, "password": "secret"},
                "logging": {"level": "debug", "file": "/var/log/app.log"},
            }
        }

        config = self.LayeredTestConfig(layer1, layer2)

        expected_settings = {
            "database": {"host": "localhost", "port": 5432, "password": "secret"},
            "logging": {"level": "debug", "file": "/var/log/app.log"},
        }
        assert config.settings == expected_settings

    def test_layered_mixin_field_filtering(self):
        """Test that only valid fields are processed."""
        layer1 = {"name": "valid_field", "invalid_field": "should_be_ignored", "nested": {"key": "valid_nested"}}

        config = self.LayeredTestConfig(layer1)

        assert config.name == "valid_field"
        assert config.nested == {"key": "valid_nested"}
        # invalid_field should be ignored
        assert not hasattr(config, "invalid_field")

    def test_layered_mixin_reverse_order_processing(self):
        """Test that layers are processed in reverse order (last wins)."""
        layer1 = {"name": "first"}
        layer2 = {"name": "second", "value": 2}
        layer3 = {"name": "third"}

        config = self.LayeredTestConfig(layer1, layer2, layer3)

        assert config.name == "first"
        assert config.value == 2

    def test_layered_mixin_with_dataclass_subconfigs(self):
        """Test layered config with dataclass subconfigs."""

        @dataclass
        class SubConfig:
            enabled: bool = False
            timeout: int = 30

        @dataclass
        class ConfigWithSubconfig:
            name: str = "default"
            subconfig: SubConfig = field(default_factory=SubConfig)

        class LayeredConfigWithSubconfig(LayeredMixin, ConfigWithSubconfig):
            pass

        layer1 = {"name": "layer1", "subconfig": {"enabled": True, "timeout": 60}}
        layer2 = {"subconfig": {"enabled": False}}

        config = LayeredConfigWithSubconfig(layer1, layer2)

        assert config.name == "layer1"
        assert isinstance(config.subconfig, SubConfig)
        assert config.subconfig.enabled is True
        assert config.subconfig.timeout == 60
