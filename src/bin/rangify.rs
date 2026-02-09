use std::ops::Range;

use clap::Parser;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Converts a .nam file to a list of ranges
struct Args {
    nam_file: String,
}

fn main() {
    let args = Args::parse();
    let nam_file = std::fs::read_to_string(args.nam_file).expect("Failed to read nam file");
    let mut sequences: Vec<Range<u32>> = Vec::new();
    for line in nam_file.lines() {
        let line = line
            .trim_start_matches("0x")
            .split_ascii_whitespace()
            .next()
            .unwrap_or("");
        let Ok(codepoint) = u32::from_str_radix(line, 16) else {
            println!("Warning: Skipping invalid line: {}", line);
            continue;
        };
        if let Some(last) = sequences.last_mut()
            && last.end == codepoint
        {
            last.end += 1;
            continue;
        }
        sequences.push(codepoint..codepoint + 1);
    }
    for range in sequences {
        if range.start + 1 == range.end {
            println!("0x{:04X}", range.start);
        } else {
            println!("0x{:04X}-0x{:04X}", range.start, range.end - 1);
        }
    }
}
