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
