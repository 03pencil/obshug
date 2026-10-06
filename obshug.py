#!/usr/bin/env python3
"""
ObsHug

Obsidian to Hugo (Hextra) Sync Script

Author: M.Hirvonen 2026
Licence: MIT
AI usage: Heavily vibe coded with le mistral & chatgpt 5.1

Copies markdown files from Obsidian's content folder to Hugo's content folder,
and copies ONLY those images from Obsidian's attachments folder that are
actually referenced in markdown.

- Obsidian is read-only (no changes in Obsidian)
- Hugo content structure mirrors Obsidian content structure
  - Exept images are moved to same folder as corresponding .md
- Existing files in Hugo are overwritten (rsync-like)

Usage:
    python obshug.py [settings.toml]
     - Put settings.toml to same folder as obshug.py

Requires Python 3.11+ (for tomllib)
"""

import re
import shutil
from pathlib import Path
import tomllib
from typing import Set, Tuple


class ObsidianToHugoSync:
    """Sync Obsidian content and used attachments to Hugo content directory."""

    def __init__(self, settings_path: Path):
        self.settings = self._load_settings(settings_path)

        # Obsidian content root (your "content" folder)
        self.obsidian_content = Path(
            self.settings["paths"]["obsidian_vault"]
        ).expanduser()

        # Hugo content root
        self.hugo_content = Path(
            self.settings["paths"]["hugo_content_dir"]
        ).expanduser()

        # Obsidian attachments root (at Obsidian vault root)
        self.attachments = Path(self.settings["paths"]["attachments_dir"]).expanduser()

        # Validate paths (read-only on Obsidian)
        if not self.obsidian_content.exists():
            raise FileNotFoundError(
                f"Obsidian content folder not found: {self.obsidian_content}"
            )
        if not self.attachments.exists():
            raise FileNotFoundError(
                f"Attachments directory not found: {self.attachments}"
            )
        if not self.hugo_content.exists():
            self.hugo_content.mkdir(parents=True)

        # Counters for summary
        self.copied_markdown = 0
        self.copied_images = 0

        # Set of (original image ref, cleaned image ref, markdown dir)
        self.used_images: Set[Tuple[str, str, Path]] = set()

    @staticmethod
    def _load_settings(path: Path) -> dict:
        """Load settings from TOML file."""
        if not path.exists():
            raise FileNotFoundError(f"Settings file not found: {path}")
        with path.open("rb") as f:
            return tomllib.load(f)

    @staticmethod
    def _is_markdown(path: Path) -> bool:
        """Check if file is markdown."""
        return path.suffix.lower() == ".md"

    @staticmethod
    def _is_image(path: Path) -> bool:
        """Check if file is an image."""
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        return path.suffix.lower() in image_extensions

    def _copy_file(self, src: Path, dest: Path) -> None:
        """Copy file from src to dest, overwriting if it exists."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    # ------------------------------------------------------------------
    # Markdown processing and image reference collection
    # ------------------------------------------------------------------

    def _clean_filename(self, filename: str) -> str:
        """Remove spaces from filename while preserving extension."""
        path = Path(filename)
        return str(path.with_stem(path.stem.replace(" ", "")))

    def _process_markdown(self, content: str, md_dir: Path) -> str:
        """
        Process markdown content:

        - Convert Obsidian wikilinks [[link]] or [[link | alt-text]] to markdown links:
          [[link]]            -> [link](link)
          [[link | alt-text]] -> [alt-text](link)

        - Convert embedded images ![[image.png]] to standard markdown images:
          ![[image.png]] -> ![image](image.png)

        While processing, collect referenced image paths so we can later
        copy only those images from attachments.
        """

        # Standard markdown images: ![alt](path/to/image.png)
        def collect_standard_images(text: str) -> None:
            pattern = re.compile(r"!\[[^\]]*]\(([^)]+)\)")
            for match in pattern.finditer(text):
                img_path = match.group(1).strip()
                clean_path = self._clean_filename(img_path)
                if self._is_image(Path(clean_path)):
                    # Store original ref, cleaned ref, and markdown directory
                    self.used_images.add((img_path, clean_path, md_dir))

        # Convert wikilinks [[link]] or [[link | alt-text]] to markdown links
        def replace_wikilink(match: re.Match) -> str:
            inner = match.group(1)

            # Convention: [[link | alt-text]]
            if "|" in inner:
                link, text = inner.split("|", 1)
                link = link.strip()
                text = text.strip()
            else:
                link = inner.strip()
                text = link

            # If link looks like an image filename
            if self._is_image(Path(link)):
                clean_link = self._clean_filename(link)
                self.used_images.add((link, clean_link, md_dir))
                return f"![{text}]({clean_link})"

            # If link has no extension, assume it's a markdown file and add .md
            if Path(link).suffix == "":
                link_with_ext = link + ".md"
            else:
                link_with_ext = link

            # Strip .md extension for final URL/path handling
            if link_with_ext.endswith(".md"):
                link_no_ext = link_with_ext[:-3]
            else:
                link_no_ext = link_with_ext

            # Example Hugo URL correction for about page:
            # Obsidian: /content/about/index.fi(.md) Chnge if you have different languages like fr
            # Hugo URL: /about/
            if "content/about/" in link_no_ext and link_no_ext.endswith("index.fi"):
                href = "/about/"
            elif "content/about/" in link_no_ext and link_no_ext.endswith("index.en"):
                href = "/about/"
            else:
                href = link_no_ext

            return f"[{text}]({href})"

        # Capture everything inside [[...]] as one group
        content = re.sub(
            r"\[\[([^\]]+)\]\]",
            replace_wikilink,
            content,
        )

        # Convert embedded images ![[image.png]] to ![image](image.png)
        def replace_embedded_image(match: re.Match) -> str:
            image_path = match.group(1).strip()
            clean_path = self._clean_filename(image_path)
            alt = Path(clean_path).stem  # minimal alt from filename
            self.used_images.add((image_path, clean_path, md_dir))
            return f"![{alt}]({clean_path})"

        content = re.sub(
            r"!\[\[([^\]]+)\]\]",
            replace_embedded_image,
            content,
        )

        # Handle malformed !![alt](path) syntax
        def replace_malformed_image(match: re.Match) -> str:
            alt = match.group(1).strip()
            path = match.group(2).strip()
            clean_alt = alt.replace(" ", "")
            clean_path = self._clean_filename(path)
            self.used_images.add((path, clean_path, md_dir))
            return f"![{clean_alt}]({clean_path})"

        content = re.sub(
            r"!!\[([^\]]+)\]\(([^)]+)\)",
            replace_malformed_image,
            content,
        )

        # Collect standard markdown image references after transformations
        collect_standard_images(content)

        return content

    # ------------------------------------------------------------------
    # Sync operations
    # ------------------------------------------------------------------

    def _sync_markdown(self, src_path: Path) -> None:
        """
        Sync a single markdown file from Obsidian content to Hugo content.

        Obsidian is read-only; we only write to Hugo.
        """
        rel_path = src_path.relative_to(self.obsidian_content)
        dest_path = self.hugo_content / rel_path

        content = src_path.read_text(encoding="utf-8")
        # Pass the destination markdown directory so images can be placed there
        content = self._process_markdown(content, md_dir=dest_path.parent)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")
        self.copied_markdown += 1

    def _sync_used_images_from_attachments(self) -> None:
        """
        Copy only those images from the attachments folder that were referenced
        in any markdown file, and rename them to remove spaces.

        Images are copied into the same folder as the markdown file
        that references them.
        """

        if not self.used_images:
            print("No images referenced in markdown; skipping attachment copy.")
            return

        # Collect all files under attachments for lookup
        attachments_files = [p for p in self.attachments.rglob("*") if p.is_file()]
        attachments_by_rel = {
            str(p.relative_to(self.attachments)): p for p in attachments_files
        }
        attachments_by_name = {p.name: p for p in attachments_files}

        copied_set: set[Path] = set()

        for original_ref, clean_ref, md_dir in sorted(self.used_images):
            ref_path = Path(original_ref)
            clean_path = Path(clean_ref)

            # Try to resolve the original referenced image
            src: Path | None = None

            # Case 1: treat as relative path under attachments
            rel_str = str(ref_path)
            src = attachments_by_rel.get(rel_str)

            # Case 2: if not found, try bare filename anywhere in attachments
            if src is None:
                src = attachments_by_name.get(ref_path.name)

            if src is None or not src.exists() or not self._is_image(src):
                print(
                    f"[WARN] Referenced image not found in attachments: {original_ref}"
                )
                continue

            # Destination: same folder as markdown that referenced this image
            dest = md_dir / clean_path.name

            if src not in copied_set:
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Copy and rename the file
                temp_dest = dest.parent / f"temp_{clean_path.name}"
                shutil.copy2(src, temp_dest)
                temp_dest.rename(dest)
                copied_set.add(src)
                self.copied_images += 1

    def run(self) -> None:
        """Run the sync process."""
        print(f"Syncing from Obsidian content: {self.obsidian_content}")
        print(f"To Hugo content:              {self.hugo_content}")
        print(f"Attachments root:             {self.attachments}")

        # 1. Sync all markdown files under Obsidian content and collect image references
        for md_file in self.obsidian_content.rglob("*.md"):
            self._sync_markdown(md_file)

        # 2. Copy only those images from attachments that were actually used
        self._sync_used_images_from_attachments()

        print("\nSync complete!")
        print(f"- Copied {self.copied_markdown} markdown files")
        print(f"- Copied {self.copied_images} image files (only those referenced)")


def main() -> None:
    """Main entry point."""
    import sys

    # Determine settings file path
    if len(sys.argv) > 1:
        settings_path = Path(sys.argv[1])
    else:
        # Try default locations
        for candidate in (
            Path(__file__).parent / "settings.toml",
            Path.cwd() / "settings.toml",
        ):
            if candidate.exists():
                settings_path = candidate
                break
        else:
            print("Error: settings.toml not found")
            print("Usage: python obshug.py [settings.toml]")
            sys.exit(1)

    try:
        sync = ObsidianToHugoSync(settings_path)
        sync.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
