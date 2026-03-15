use std::path::PathBuf;

use clap::{Parser, Subcommand};
use openmodels_rs::{
    canonical_model_to_pretty_json, canonical_model_to_value, generate_artifacts_to_directory,
    generate_drizzle_schema, list_adapters, load_openapi_document, normalize_openapi_document,
    write_json_file,
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
    Generate {
        #[arg(long)]
        input: PathBuf,
        #[arg(long = "out-dir")]
        out_dir: PathBuf,
        #[arg(long)]
        filename: Option<String>,
        #[arg(long, value_parser = parse_target)]
        target: Option<String>,
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
        Command::Generate {
            input,
            out_dir,
            filename,
            target,
        } => {
            let written_paths = generate_artifacts_to_directory(
                input,
                out_dir,
                target.as_deref(),
                filename.as_deref(),
            )?;
            for path in written_paths {
                if let Some(target) = target.as_deref() {
                    println!("Generated {} artifact: {}", target, path.display());
                } else {
                    println!("Generated declared artifact: {}", path.display());
                }
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

fn parse_target(value: &str) -> std::result::Result<String, String> {
    if list_adapters().iter().any(|adapter| adapter.key() == value) {
        Ok(value.to_owned())
    } else {
        Err(format!("unsupported target '{}'", value))
    }
}
