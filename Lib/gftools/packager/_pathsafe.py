"""Helpers for safely joining untrusted, metadata-supplied paths.

``METADATA.pb`` / ``upstream.yaml`` ``source.files[].dest_file`` values are
contributor-controlled (they arrive with the family being on-boarded). They are
used to build the destination path that downloaded/built assets are written to.
Without validation, a ``dest_file`` such as ``../../../.git/hooks/post-checkout``
or an absolute path escapes the intended family directory, allowing an arbitrary
file write on the machine of whoever runs ``gftools packager`` on the family.

``safe_join`` constrains the result to stay inside ``root``.
"""

from pathlib import Path


def safe_join(root, rel) -> Path:
    """Join ``rel`` onto ``root`` and ensure the result stays inside ``root``.

    Raises ``ValueError`` if ``rel`` is absolute or uses ``..`` traversal to
    escape ``root``.
    """
    root_resolved = Path(root).resolve()
    candidate = Path(root, rel).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(
            f"Refusing to write outside the target directory: dest_file {rel!r} "
            f"resolves to '{candidate}', which is outside '{root_resolved}'."
        )
    return candidate
