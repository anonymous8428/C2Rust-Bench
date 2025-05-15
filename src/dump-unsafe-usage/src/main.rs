//! Parse a Rust source file into a `syn::File` and print out a debug
//! representation of the syntax tree.
//!
//! Use the following command from this directory to test this program by
//! running it on its own source code:
//!
//!     cargo run -- src/main.rs
//!
//! The output will begin with:
//!
//!     File {
//!         shebang: None,
//!         attrs: [
//!             Attribute {
//!                 pound_token: Pound,
//!                 style: AttrStyle::Inner(
//!         ...
//!     }

use colored::Colorize;
use std::borrow::Cow;
use std::env;
use std::ffi::OsStr;
use std::fmt::{self, Display};
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process;
use syn::Block;
// use syn::Stmt;
use syn::Expr;
// use syn::Stmt::Expr;

enum Error {
    IncorrectUsage,
    ReadFile(io::Error),
    ParseFile {
        error: syn::Error,
        filepath: PathBuf,
        source_code: String,
    },
}

impl Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Error::IncorrectUsage => write!(f, "Usage: dump-syntax path/to/filename.rs"),
            Error::ReadFile(error) => write!(f, "Unable to read file: {}", error),
            Error::ParseFile {
                error,
                filepath,
                source_code,
            } => render_location(f, error, filepath, source_code),
        }
    }
}

fn main() {
    if let Err(error) = try_main() {
        let _ = writeln!(io::stderr(), "{}", error);
        process::exit(1);
    }
}

fn try_main() -> Result<(), Error> {
    let mut args = env::args_os();
    let _ = args.next(); // executable name

    let filepath = match (args.next(), args.next()) {
        (Some(arg), None) => PathBuf::from(arg),
        _ => return Err(Error::IncorrectUsage),
    };

    let code = fs::read_to_string(&filepath).map_err(Error::ReadFile)?;
    let syntax = syn::parse_file(&code).map_err({
        |error| Error::ParseFile {
            error,
            filepath,
            source_code: code,
        }
    })?;

    // println!("{:#?}", syntax);
    for item in syntax.items {
        if let syn::Item::Fn(func) = item {
            // println!("Function: {}", func.sig.ident);
            // if let Some(block) = func.block {
            //     count_unsafe_statements(&block);
            // }
            let (unsafe_block_count, res_list) = count_unsafe_statements(&func.block);
            let formatted_res = res_list.iter()
                                .map(|res| res.to_string())
                                .collect::<Vec<String>>()
                                .join(";");
            println!("{};{};{}", func.sig.ident, unsafe_block_count, formatted_res);

            // println!("Val: {}", res_list[0]);
            // println!("Val: {}", res_list[1]);

        }
    }

    Ok(())
}
fn count_unsafe_statements(block: &Block) -> (usize, Vec<usize>) {
    let mut unsafe_block_count = 0;
    let mut res_list = Vec::new();

    for stmt in &block.stmts {
        // println!("Found a statement: {:?}", stmt);
        match stmt {
            // Check if the statement is inside an unsafe block
            syn::Stmt::Expr(Expr::Unsafe(asd), None) => {
                unsafe_block_count += 1;
                let res = count_statements_in_block(&asd.block);
                res_list.push(res);
                // println!("res: {}", res);
            }

            _ => {}
        }
    }
    // println!("Total number of unsafe block {}", unsafe_block_count);
    (unsafe_block_count, res_list)
}

fn count_statements_in_block(block: &Block) -> usize {
    let mut count = 0;

    for stmt in &block.stmts {
        match stmt {
            syn::Stmt::Expr(Expr::Loop(expr), _) => {
                count += 1;
                count += count_statements_in_block(&expr.body);
            }
            syn::Stmt::Expr(Expr::If(expr), _) => {
                if let cond_block = &expr.then_branch {
                    count += 1;
                    count += count_statements_in_block(&expr.then_branch);
                }
                if let Some((_, else_expr)) = &expr.else_branch {
                    count += 1;
                    if let Expr::Block(else_block) = &**else_expr {
                        count += count_statements_in_block(&else_block.block);
                    }
                }
            }
            syn::Stmt::Expr(Expr::Block(expr), _) => {
                // count += 1;
                count += count_statements_in_block(&expr.block);
            }
            syn::Stmt::Expr(Expr::Match(expr), _) => {
                count += 1;
                for arm in &expr.arms {
                    count += 1;
                    if let Expr::Block(arm_block) = &*arm.body {
                        count += count_statements_in_block(&arm_block.block);
                    }
                }
            }
            syn::Stmt::Expr(Expr::While(expr), _) => {
                // Handle while loop
                count += 1;
                count += count_statements_in_block(&expr.body);
            }

            syn::Stmt::Expr(Expr::ForLoop(expr), _) => {
                count += 1;
                count += count_statements_in_block(&expr.body);
            }

            syn::Stmt::Expr(Expr::TryBlock(expr), _) => {
                count += 1;
                count += count_statements_in_block(&expr.block);
            }

            syn::Stmt::Expr(Expr::Try(expr), _) => {
                count += 1;
            }
            syn::Stmt::Expr(Expr::Unsafe(expr), None) => {
                count += 1;
                count += count_statements_in_block(&expr.block);
            }
            // Stmt::Local is currently not handled seperately. It is counted as 1.
            _ => {count += 1;}  // Other statements are counted as 1
        }
    }

    count
}


fn render_location(
    formatter: &mut fmt::Formatter,
    err: &syn::Error,
    filepath: &Path,
    code: &str,
) -> fmt::Result {
    let start = err.span().start();
    let mut end = err.span().end();

    let code_line = match start.line.checked_sub(1).and_then(|n| code.lines().nth(n)) {
        Some(line) => line,
        None => return render_fallback(formatter, err),
    };

    if end.line > start.line {
        end.line = start.line;
        end.column = code_line.len();
    }

    let filename = filepath
        .file_name()
        .map(OsStr::to_string_lossy)
        .unwrap_or(Cow::Borrowed("main.rs"));

    write!(
        formatter,
        "\n\
         {error}{header}\n\
         {indent}{arrow} {filename}:{linenum}:{colnum}\n\
         {indent} {pipe}\n\
         {label} {pipe} {code}\n\
         {indent} {pipe} {offset}{underline} {message}\n\
         ",
        error = "error".red().bold(),
        header = ": Syn unable to parse file".bold(),
        indent = " ".repeat(start.line.to_string().len()),
        arrow = "-->".blue().bold(),
        filename = filename,
        linenum = start.line,
        colnum = start.column,
        pipe = "|".blue().bold(),
        label = start.line.to_string().blue().bold(),
        code = code_line.trim_end(),
        offset = " ".repeat(start.column),
        underline = "^"
            .repeat(end.column.saturating_sub(start.column).max(1))
            .red()
            .bold(),
        message = err.to_string().red(),
    )
}

fn render_fallback(formatter: &mut fmt::Formatter, err: &syn::Error) -> fmt::Result {
    write!(formatter, "Unable to parse file: {}", err)
}
