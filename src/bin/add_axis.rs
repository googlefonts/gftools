use clap::{Arg, Command};
use fontations::skrifa::{Axis, AxisCollection, FontRef, MetadataProvider};
use gf_metadata::AxisProto;

fn choose_axis(axes: &AxisCollection, font: &FontRef) -> fontations::skrifa::Axis {
    loop {
        for (index, axis) in axes.iter().enumerate() {
            println!(
                "{}) {}: {}",
                index + 1,
                axis.tag(),
                font.localized_strings(axis.name_id())
                    .english_or_first()
                    .map(|x| x.to_string())
                    .unwrap_or_default()
            );
        }
        let mut input = String::new();
        std::io::stdin()
            .read_line(&mut input)
            .expect("error: unable to read user input");
        if let Ok(choice) = input.trim_end().parse::<usize>() {
            if choice > 0 && choice < axes.len() {
                return axes.iter().nth(choice - 1).unwrap();
            } else {
                eprintln!("Invalid choice, please try again.");
            }
        } else {
            eprintln!("Invalid input, please enter a number.");
        }
    }
}

fn main() {
    let matches = Command::new("gftools-add-axis")
        .version(env!("CARGO_PKG_VERSION"))
        .about("Create or author Google Fonts axisregistry {AXIS_NAME}.textproto files.")
        .arg(
            Arg::new("FONT")
                .help("The font file to get the axis values from")
                .required(true)
                .index(1),
        )
        .get_matches();
    let font_path = matches.get_one::<String>("FONT").unwrap();
    let font_data = std::fs::read(font_path).expect("Failed to read the font file");
    let font = FontRef::new(&font_data).expect("Failed to parse the font file");
    let axes = font.axes();
    if axes.is_empty() {
        eprintln!("No axes found in the font.");
        return;
    }
    let chosen_axis: Axis = choose_axis(&axes, &font);
    println!("Chosen axis: {}", chosen_axis.tag());
    let axis_name = font
        .localized_strings(chosen_axis.name_id())
        .english_or_first()
        .map(|x| x.to_string())
        .unwrap_or_default();
    // let axis_proto = AxisProto {
    //     tag: Some(chosen_axis.tag().to_string()),
    //     display_name: axis_name,
    //     min_value: chosen_axis.min_value(),
    //     default_value: chosen_axis.default_value(),
    //     max_value: chosen_axis.max_value(),
    //     precision: chosen_axis.precision(),
    //     fallback: chosen_axis.fallback(),
    //     description: chosen_axis.description(),
    //     fallback_only: false,
    //     special_fields: None,
    //     illustration_url: None,
    // };
}
