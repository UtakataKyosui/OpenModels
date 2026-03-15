use std::path::PathBuf;

use clap::{Parser, Subcommand};
use openmodels_rs::{
    canonical_model_to_pretty_json, canonical_model_to_value, generate_drizzle_schema,
    load_openapi_document, normalize_openapi_document, write_json_file,
};

#[derive(Debug, Parser)]
#[command(
    name = "openmodels-rs",
    about = "Rust bootstrap for OpenModels normalization"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    Normalize {
        #[arg(long)]
        input: PathBuf,
        #[arg(long)]
        out: Option<PathBuf>,
    },
    GenerateDrizzle {
        #[arg(long)]
        input: PathBuf,
        #[arg(long)]
        out: Option<PathBuf>,
    },
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}

fn run() -> openmodels_rs::Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Normalize { input, out } => {
            let document = load_openapi_document(input)?;
            let canonical = normalize_openapi_document(&document)?;
            if let Some(out_path) = out {
                write_json_file(out_path, &canonical_model_to_value(&canonical)?)?;
            } else {
                print!("{}", canonical_model_to_pretty_json(&canonical)?);
            }
        }
        Command::GenerateDrizzle { input, out } => {
            let document = load_openapi_document(input)?;
            let canonical = normalize_openapi_document(&document)?;
            let schema = generate_drizzle_schema(&canonical)?;
            if let Some(out_path) = out {
                if let Some(parent) = out_path.parent() {
                    std::fs::create_dir_all(parent)?;
                }
                std::fs::write(out_path, schema)?;
            } else {
                print!("{schema}");
            }
        }
    }
    Ok(())
}
