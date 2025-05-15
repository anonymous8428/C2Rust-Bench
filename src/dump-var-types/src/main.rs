use std::env;
use std::fs;
use syn::{parse_file, ItemFn, Pat, FnArg, Stmt, Expr, ReturnType};
use quote::ToTokens; // Import ToTokens for the token stream conversion

fn main() {
    // Get the file path from command-line arguments
    let args: Vec<String> = env::args().collect();

    if args.len() != 2 {
        eprintln!("Usage: dump-var-types <path-to-rust-file>");
        std::process::exit(1);
    }

    let file_path = &args[1];

    // Read the content of the file
    let code = fs::read_to_string(file_path)
        .expect("Unable to read file");

    // Parse the Rust code into an abstract syntax tree (AST)
    let ast = parse_file(&code).expect("Failed to parse code");

    // Iterate over the items (like functions) in the AST
    for item in ast.items {
        if let syn::Item::Fn(ItemFn { sig, block, .. }) = item {
            // Get function arguments and their types
            println!("Function;{}", sig.ident);
            let inputs = &sig.inputs;
            for input in inputs {
                if let FnArg::Typed(pat_type) = input {
                    if let Pat::Ident(pat_ident) = &*pat_type.pat {
                        println!(
                            "Argument;{};{}",
                            pat_ident.ident,
                            pat_type.ty.clone().into_token_stream().to_string()
                        );
                    }
                }
            }

            // Get the return type of the function
            if let syn::ReturnType::Type(_, return_type) = &sig.output {
                println!("Return;{}", return_type.clone().into_token_stream().to_string());
            }

            // Get types of local variables inside the function body
            // println!("\nLocal variable types:");
            for stmt in &block.stmts {
                match stmt {
                    // Handle let statements
                    Stmt::Local(local) => {
                        if let Some((_, init)) = &local.init {
                            // Print the pattern and type if available
                            if let Pat::Ident(pat_ident) = &local.pat {
                                // Try to extract type information from the initialization expression
                                println!(
                                    "Local;{};{}",
                                    pat_ident.ident,
                                    get_type_of_expression(init)
                                );
                            } else if let Pat::Type(pat_type) = &local.pat {
                                if let Pat::Ident(pat_ident) = &*pat_type.pat {
                                    // Check if the type is an array
                                    if let syn::Type::Array(_) = &*pat_type.ty {
                                        println!(
                                            "Local;{};array#{}",
                                            pat_ident.ident,
                                            pat_type.ty.to_token_stream().to_string()
                                        );
                                    }
                                    // Check if the type is a tuple
                                    else if let syn::Type::Tuple(_) = &*pat_type.ty {
                                        println!(
                                            "Local;{};tuple#{}",
                                            pat_ident.ident,
                                            pat_type.ty.to_token_stream().to_string()
                                        );
                                    }
                                    // // Check if the type is a Vec
                                    // else if let syn::Type::Path(type_path) = &*pat_type.ty {
                                    //     if type_path.path.is_ident("Vec") {
                                    //         println!(
                                    //             "Local;{};Vec",
                                    //             pat_ident.ident
                                    //         );
                                    //     }
                                    // }
                                    // // Check if the type is a HashMap
                                    // else if let syn::Type::Path(type_path) = &*pat_type.ty {
                                    //     if type_path.path.is_ident("HashMap") {
                                    //         println!(
                                    //             "Local;{};HashMap",
                                    //             pat_ident.ident
                                    //         );
                                    //     }
                                    // }
                                    // For other types, print the type
                                    else {
                                        println!(
                                            "Local;{};{}",
                                            pat_ident.ident,
                                            pat_type.ty.to_token_stream().to_string()
                                        );
                                    }
                                }
                            }
                        }
                    }
                    // // Handle assignment statements
                    // Stmt::Expr(expr) | Stmt::Semi(expr, _) => {
                    //     if let Expr::Assign(assign) = expr {
                    //         if let Expr::Path(expr_path) = &*assign.left {
                    //             if let Some(ident) = expr_path.path.get_ident() {
                    //                 println!(
                    //                     "Assigned variable: {} with type {}",
                    //                     ident,
                    //                     get_type_of_expression(&assign.right)
                    //                 );
                    //             }
                    //         }
                    //     }
                    // }
                    _ => {} // Ignore other statement types
                }
            }
        }
    }
}

/// Helper function to determine the type of an expression
fn get_type_of_expression(expr: &Expr) -> String {
    match expr {
        Expr::Path(path) => {
            // Check if the path has segments
            // println!("ExprPath: {}", first_segment.ident);
            if let Some(first_segment) = path.path.segments.first() {
                // Print the first segment's identifier (name of the enum or type)
                // return first_segment.ident.to_string();
                return format!("enum#{}", first_segment.ident.to_string());
            }
            "NotIdentified#ExprPath".to_string()
        }
        Expr::Lit(lit) => {
            println!("ExprLit");
            match &lit.lit {
                syn::Lit::Int(_) => "int".to_string(),
                syn::Lit::Float(_) => "float".to_string(),
                syn::Lit::Str(_) => "string".to_string(),  // For string literals
                syn::Lit::Char(_) => "char".to_string(),   // For character literals
                syn::Lit::Bool(_) => "bool".to_string(),   // For boolean literals
                syn::Lit::Byte(_) => "u8".to_string(),     // For byte literals (b'a')
                syn::Lit::ByteStr(_) => "Vec<u8>".to_string(), // For byte string literals (b"hello")
                syn::Lit::Verbatim(_) => "Verbatim Literal".to_string(),
                _ => "NotIdentified#ExprLit".to_string(),
            }
            
        }
        Expr::Unary(unary) => {
            // println!("ExprUnary");
            format!("{}", get_type_of_expression(&unary.expr))
        }
        // Expr::Binary(binary) => {
        //     println!("ExprBinary");
        //     format!(
        //         "{} -- {}",
        //         get_type_of_expression(&binary.left),
        //         get_type_of_expression(&binary.right)
        //     )
        // }
        Expr::Call(call) => {
            // Check if it's a closure or a function call
            // println!("ExprCall");
            "NotIdentified#ExprCall".to_string()
        }
        Expr::Closure(closure) => {
            // println!("ExprClosure");
            // Check if there are arguments in the closure (closure.inputs)
            if let Some(first_arg) = closure.inputs.first() {
                if let Pat::Type(pat_type) = first_arg {
                    // If the argument has an explicit type, extract it
                    return pat_type.ty.to_token_stream().to_string();
                }
                
            }
            "NotIdentified#ExprClosure".to_string()
        }

        Expr::Macro(macro_expr) => {
            if let Some(ident) = macro_expr.mac.path.get_ident() {
                if ident == "format" {
                    return "string".to_string();
                }
            }
            "NotIdentified#ExprMacro".to_string()
        }

        Expr::Array(array) => {
            let num_elements = array.elems.len();
            if let Some(first_elem) = array.elems.first() {
                // Get the type of the first element (assuming all elements are of the same type)
                let element_type = get_type_of_expression(first_elem);
                return format!("array#[{}; {}]", element_type, num_elements);
            }
            "array#[]".to_string()
        }
        
        Expr::Tuple(tuple) => {
            let element_types: Vec<String> = tuple.elems.iter()
                .map(|elem| get_type_of_expression(elem)) // Get type for each element
                .collect();
            
            if !element_types.is_empty() {
                return format!("tuple#({})", element_types.join(", "));
            }
            "tuple#()".to_string()
        }

        Expr::Struct(struct_expr) => {
            if let Some(ident) = struct_expr.path.get_ident() {
                let struct_name = ident.to_string();
                // Assuming the struct has fields, we print the name of the first field.
                // Check if the first field is a named field (it should be, like 'name' or 'age').
                if let Some(first_field) = struct_expr.fields.first() {
                    if let syn::Member::Named(ident) = &first_field.member {
                        return format!("struct#{}", struct_name);
                    }
                }
            }
            "NotIdentified#Struct".to_string()
        }

        _ => "NotIdentified#Expression".to_string(),
    }
}
