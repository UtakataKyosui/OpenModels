use serde_json::Value;

pub fn snake_case(value: &str) -> String {
    let chars = value.chars().collect::<Vec<_>>();
    let mut output = String::new();

    for (index, ch) in chars.iter().enumerate() {
        let previous = index.checked_sub(1).and_then(|item| chars.get(item));
        let next = chars.get(index + 1);

        if ch.is_ascii_uppercase() {
            let needs_separator = previous.is_some_and(|previous| {
                previous.is_ascii_lowercase()
                    || previous.is_ascii_digit()
                    || (previous.is_ascii_uppercase()
                        && next.is_some_and(|next| next.is_ascii_lowercase()))
            });
            if needs_separator && !output.ends_with('_') {
                output.push('_');
            }
            output.push(ch.to_ascii_lowercase());
            continue;
        }

        if *ch == '-' || *ch == ' ' {
            if !output.ends_with('_') {
                output.push('_');
            }
            continue;
        }

        output.push(*ch);
    }

    output
}

pub fn camel_case(value: &str) -> String {
    let mut parts = value.split(['_', '-', ' ']).filter(|part| !part.is_empty());
    let Some(first) = parts.next() else {
        return String::new();
    };

    let mut output = first.to_ascii_lowercase();
    for part in parts {
        let mut chars = part.chars();
        if let Some(ch) = chars.next() {
            output.push(ch.to_ascii_uppercase());
            output.extend(chars);
        }
    }
    output
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
