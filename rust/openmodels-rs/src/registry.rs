use crate::adapter::BackendAdapter;
use crate::drizzle::{DRIZZLE_PG_ADAPTER, DRIZZLE_PG_TARGET};
use crate::error::{Result, message};

pub fn get_adapter(target: &str) -> Result<&'static dyn BackendAdapter> {
    match target {
        DRIZZLE_PG_TARGET => Ok(&DRIZZLE_PG_ADAPTER),
        _ => Err(message(format!("Unknown adapter target '{}'.", target))),
    }
}

pub fn list_adapters() -> Vec<&'static dyn BackendAdapter> {
    vec![&DRIZZLE_PG_ADAPTER]
}
