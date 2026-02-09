use clap::Parser;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Utility to print unicode character names from a nam file.
///
/// Input file should have one codepoint per line in hex (0xXXXX).
struct Args {
    nam_file: String,
}

fn main() {
    let args = Args::parse();
    let nam_file = std::fs::read_to_string(args.nam_file).expect("Failed to read nam file");
    for line in nam_file.lines() {
        if let Ok(codepoint) = u32::from_str_radix(line.trim_start_matches("0x"), 16) {
            if let Some(name) = char::from_u32(codepoint).and_then(unicode_names2::name) {
                println!("U+{:04X}: {}", codepoint, name);
            } else {
                println!("U+{:04X}: <unknown>", codepoint);
            }
        } else {
            eprintln!("Invalid line in nam file: {}", line);
        }
    }
}
