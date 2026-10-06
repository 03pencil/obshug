# obshug
Obsidian to Gohugo script to move and modify md files from ObsidianMD directory to Hugo directory.

## Flow

Write content in ObsidianMD --> run obsgug.py --> files moved to hugo content directory

## Functions

- Obsidian Wikilinks --> Hugo links 
- Images (obsidian attacment directory) --> Hugo content directory (same as the corresponding page)

- Replaces content in Hugo content directory
- Only Read at Obsidian


## Usage

- Modify settings.toml file to correspond to your directory locations
- Run obshug.py
-   python3 obshug.py
- obshug.py and settings.toml files have to be at same directory
```

> [!CAUTION]
> Skript is replaicing files in moving operation. Make sure you know what you do!!


