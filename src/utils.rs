use crate::error::GftoolsError;

pub(crate) fn download_family_from_google_fonts(
    family: &str,
) -> Result<Vec<Vec<u8>>, GftoolsError> {
    let request = reqwest::blocking::Client::new().get(format!(
        "https://fonts.google.com/download/list?family={}",
        family.replace(" ", "%20")
    ));
    let manifest: serde_json::Value = request
        .send()
        .and_then(|response| response.text())
        .map_or_else(
            |e| {
                Err(GftoolsError::Misc(format!(
                    "Failed to fetch metadata: {}",
                    e
                )))
            },
            |s| {
                serde_json::from_str(&s[5..])
                    .map_err(|e| GftoolsError::Misc(format!("Failed to parse metadata: {}", e)))
            },
        )?;
    let mut fonts = vec![];
    for file in manifest
        .as_object()
        .and_then(|x| x.get("manifest"))
        .and_then(|x| x.as_object())
        .and_then(|x| x.get("fileRefs"))
        .and_then(|x| x.as_array())
        .ok_or(GftoolsError::Misc(format!(
            "Failed to find fileRefs in manifest: {:?}",
            manifest
        )))?
    {
        let url = file
            .as_object()
            .and_then(|x| x.get("url"))
            .and_then(|x| x.as_str())
            .ok_or(GftoolsError::Misc("Failed to find url in file".to_string()))?;
        let filename = file
            .as_object()
            .and_then(|x| x.get("filename"))
            .and_then(|x| x.as_str())
            .ok_or(GftoolsError::Misc(
                "Failed to filename url in file".to_string(),
            ))?;
        if filename.contains("static") || !filename.ends_with("otf") && !filename.ends_with("ttf") {
            continue;
        }
        let contents = reqwest::blocking::get(url)
            .map_err(|e| GftoolsError::Misc(format!("Failed to fetch font: {}", e)))?
            .bytes()
            .map_err(|e| GftoolsError::Misc(format!("Failed to fetch font: {}", e)))?;
        fonts.push(contents.to_vec());
    }
    Ok(fonts)
}
