use heck::{ToLowerCamelCase, ToSnakeCase, ToUpperCamelCase};
use serde_json::Value;

pub fn snake_case(value: &str) -> String {
    value.to_snake_case()
}

pub fn camel_case(value: &str) -> String {
    value.to_lower_camel_case()
}

pub fn upper_camel_case(value: &str) -> String {
    value.to_upper_camel_case()
}

pub fn escape_template_literal(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('`', "\\`")
        .replace("${", "\\${")
}

pub fn to_json_literal(value: &Value) -> String {
    serde_json::to_string(value).expect("json literal")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // --- snake_case ---

    #[test]
    fn snake_case_passes_through_already_snake() {
        assert_eq!("hello_world", snake_case("hello_world"));
    }

    #[test]
    fn snake_case_converts_camel_case() {
        assert_eq!("user_id", snake_case("userId"));
    }

    #[test]
    fn snake_case_converts_pascal_case() {
        assert_eq!("canonical_model", snake_case("CanonicalModel"));
    }

    #[test]
    fn snake_case_lowercases_all_caps() {
        assert_eq!("id", snake_case("ID"));
    }

    // --- camel_case ---

    #[test]
    fn camel_case_converts_snake_to_lower_camel() {
        assert_eq!("userId", camel_case("user_id"));
    }

    #[test]
    fn camel_case_leaves_already_camel_unchanged() {
        assert_eq!("userId", camel_case("userId"));
    }

    #[test]
    fn camel_case_converts_single_word_to_lowercase() {
        assert_eq!("id", camel_case("Id"));
    }

    // --- upper_camel_case ---

    #[test]
    fn upper_camel_case_converts_snake_to_pascal() {
        assert_eq!("UserId", upper_camel_case("user_id"));
    }

    #[test]
    fn upper_camel_case_capitalizes_first_letter() {
        assert_eq!("User", upper_camel_case("user"));
    }

    #[test]
    fn upper_camel_case_leaves_pascal_unchanged() {
        assert_eq!("CanonicalModel", upper_camel_case("CanonicalModel"));
    }

    // --- escape_template_literal ---

    #[test]
    fn escape_template_literal_escapes_backtick() {
        assert_eq!("hello \\` world", escape_template_literal("hello ` world"));
    }

    #[test]
    fn escape_template_literal_escapes_dollar_brace() {
        assert_eq!("\\${value}", escape_template_literal("${value}"));
    }

    #[test]
    fn escape_template_literal_escapes_backslash() {
        assert_eq!("a\\\\b", escape_template_literal("a\\b"));
    }

    #[test]
    fn escape_template_literal_leaves_plain_string_unchanged() {
        assert_eq!("hello world", escape_template_literal("hello world"));
    }

    // --- to_json_literal ---

    #[test]
    fn to_json_literal_serializes_string() {
        assert_eq!("\"hello\"", to_json_literal(&json!("hello")));
    }

    #[test]
    fn to_json_literal_serializes_number() {
        assert_eq!("42", to_json_literal(&json!(42)));
    }

    #[test]
    fn to_json_literal_serializes_boolean() {
        assert_eq!("true", to_json_literal(&json!(true)));
    }

    #[test]
    fn to_json_literal_serializes_null() {
        assert_eq!("null", to_json_literal(&json!(null)));
    }

    #[test]
    fn to_json_literal_serializes_array() {
        assert_eq!("[1,2,3]", to_json_literal(&json!([1, 2, 3])));
    }
}
