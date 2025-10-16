#!/usr/bin/env python3
"""
Convert RamaLama manpages to Docusaurus MDX format
"""

import glob
import os
import re
from pathlib import Path


def get_category_info(filename):
    """Determine category and output path based on manpage section"""
    if filename.endswith('.1.md'):
        return 'commands', 'commands/ramalama'
    if filename.endswith('.5.md'):
        return 'configuration', 'configuration'
    if filename.endswith('.7.md'):
        return 'platform-guides', 'platform-guides'
    return 'misc', 'misc'


def extract_title_and_description(content, filename):
    """Extract title and description from manpage content and filename"""
    lines = content.split('\n')

    # Generate title from filename pattern
    base_name = os.path.basename(filename)
    title = None

    if base_name == 'ramalama.1.md':
        title = 'ramalama'  # Base command page
    elif base_name.startswith('ramalama-') and base_name.endswith('.1.md'):
        # Command pages: ramalama-chat.1.md -> chat
        title = base_name.replace('ramalama-', '').replace('.1.md', '')
    elif base_name.endswith('.7.md'):
        # Platform guides: ramalama-cuda.7.md -> CUDA Support
        title = base_name.replace('ramalama-', '').replace('.7.md', '')
    elif base_name.endswith('.5.md'):
        # Config files with custom titles
        if base_name == 'ramalama.conf.5.md':
            title = 'Configuration File'
        elif base_name == 'ramalama-oci.5.md':
            title = 'OCI Spec'
        else:
            # Fallback for other .5.md files
            title = base_name.replace('.5.md', '')

    if title is None:
        # Fallback for any other file types
        title = base_name.replace('.md', '').replace('-', ' ')

    # Find description from NAME section
    description = ""
    for i, line in enumerate(lines):
        if line.strip() == "## NAME":
            if i + 1 < len(lines):
                name_line = lines[i + 1].strip()
                if ' - ' in name_line:
                    _, description = name_line.split(' - ', 1)
                    break

    # Fallback description if not found
    if not description:
        if '.1.md' in filename:
            description = "RamaLama command reference"
        elif '.7.md' in filename:
            description = "Platform-specific setup guide"
        elif '.5.md' in filename:
            description = "Configuration file reference"
        else:
            description = "RamaLama documentation"

    return title.strip(), description.strip()


def detect_code_language(content):
    """Detect the language of a code block based on its content"""
    # Common indicators for different languages
    if re.search(r'\$\s*(podman|docker|ramalama|curl|wget|sudo|apt|dnf|yum|pacman|brew)\s', content):
        return 'bash'
    if re.search(
        r'(import\s+[a-zA-Z_][a-zA-Z0-9_]*|def\s+[a-zA-Z_][a-zA-Z0-9_]*\(|class\s+[a-zA-Z_][a-zA-Z0-9_]*:)', content
    ):
        return 'python'
    if re.search(
        r'(function\s+[a-zA-Z_$][a-zA-Z0-9_$]*\s*\(|const\s+[a-zA-Z_$][a-zA-Z0-9_$]*\s*=|let\s+[a-zA-Z_$] \
            [a-zA-Z0-9_$]*\s*=|var\s+[a-zA-Z_$][a-zA-Z0-9_$]*\s*=)',
        content,
    ):
        return 'javascript'
    if re.search(
        r'(package\s+[a-zA-Z_][a-zA-Z0-9_]*|func\s+[a-zA-Z_][a-zA-Z0-9_]*\(|type\s+[a-zA-Z_][a-zA-Z0-9_]*\s+struct)',
        content,
    ):
        return 'go'
    if re.search(r'(\[.*\]|\{.*\})\s*=', content):
        return 'toml'

    return 'text'


def convert_markdown_to_mdx(content, filename, current_output_path, output_map):
    """Convert manpage markdown to MDX format"""

    # Extract title and description
    title, description = extract_title_and_description(content, filename)

    # Remove the first line (% directive) if present
    lines = content.split('\n')
    if lines[0].startswith('%'):
        lines = lines[1:]

    content = '\n'.join(lines)

    # Remove NAME section (handles both H1 and H2 variants)
    content = re.sub(
        r'^#{1,2}\s+NAME\s*\n(?:.*?)(?=^#{1,6}\s|\Z)',
        '',
        content,
        flags=re.MULTILINE | re.DOTALL,
    )

    # Convert SYNOPSIS to proper heading
    content = re.sub(r'## SYNOPSIS', '## Synopsis', content)

    # Convert DESCRIPTION
    content = re.sub(r'## DESCRIPTION', '## Description', content)

    # Convert OPTIONS to Options
    content = re.sub(r'## OPTIONS', '## Options', content)

    # Convert EXAMPLES to Examples
    content = re.sub(r'## EXAMPLES', '## Examples', content)

    # Convert SEE ALSO to See Also
    content = re.sub(r'## SEE ALSO', '## See Also', content)

    # Convert HISTORY to bottom note
    history_pattern = r'## HISTORY\n(.+?)(?=\n##|\n$|$)'
    history_match = re.search(history_pattern, content, re.DOTALL)
    if history_match:
        history_text = history_match.group(1).strip()
        content = re.sub(history_pattern, '', content, flags=re.DOTALL)
        # Remove TOC links to HISTORY since it becomes a footer
        content = re.sub(r'\s*- \[HISTORY\]\(#history\)\n?', '', content)
        # Add history as footer
        content += f"\n\n---\n\n*{history_text}*"

    # Convert bold markdown references like **[ramalama(1)](ramalama.1.md)** to links
    content = re.sub(r'\*\*\[([^\]]+)\]\(([^)]+)\)\*\*', r'[\1](\2)', content)

    def convert_link(match):
        text = match.group(1)
        link = match.group(2)

        # Skip processing for external URLs
        if link.startswith(('http://', 'https://')):
            return f'[{text}]({link})'

        base_link = os.path.basename(link)
        target_rel_path = output_map.get(base_link)

        if not target_rel_path:
            return f'[{text}]({link})'

        target_path = target_rel_path

        if target_path == current_output_path:
            return f'[{text}](#)'  # Self-reference

        if target_path == Path('commands/ramalama/ramalama.mdx'):
            return f'[{text}](/docs/commands/ramalama/)'

        # Use absolute doc URL (prefix with /docs)
        target_route = '/docs/' + target_path.with_suffix('').as_posix()

        return f'[{text}]({target_route})'

    content = re.sub(r'\[([^\]]+)\]\(([^)]+\.md)\)', convert_link, content)

    # Convert Notes to MDX admonitions
    # Handle blockquote notes: > **Note:** text
    content = re.sub(
        r'  > \*\*Note:\*\*(.*?)(?=\n(?!  >)|\n\n|$)', r':::note\n\1\n:::', content, flags=re.MULTILINE | re.DOTALL
    )
    content = re.sub(
        r'> \*\*Note:\*\*(.*?)(?=\n(?!>)|\n\n|$)', r':::note\n\1\n:::', content, flags=re.MULTILINE | re.DOTALL
    )
    # Handle blockquote NOTE (all caps): > **NOTE:** text
    content = re.sub(
        r'  > \*\*NOTE:\*\*(.*?)(?=\n(?!  >)|\n\n|$)', r':::note\n\1\n:::', content, flags=re.MULTILINE | re.DOTALL
    )
    content = re.sub(
        r'> \*\*NOTE:\*\*(.*?)(?=\n(?!>)|\n\n|$)', r':::note\n\1\n:::', content, flags=re.MULTILINE | re.DOTALL
    )
    # Handle standalone Note: followed by content (possibly with blank lines)
    content = re.sub(
        r'^Note:\s*\n\n(.*?)(?=\n\nNote:|\n\n[A-Z][A-Z]|\n\n##|$)',
        r':::note\n\1\n:::',
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    # Handle standalone Note: with immediate content
    content = re.sub(
        r'^Note:(.*?)(?=\n\nNote:|\n\n[A-Z][A-Z]|\n\n##|$)',
        r':::note\n\1\n:::',
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    # Handle NOTE: text (all caps)
    content = re.sub(r'^NOTE:(.*?)(?=\n\n|\n[A-Z]|\n#|$)', r':::note\n\1\n:::', content, flags=re.MULTILINE | re.DOTALL)

    # Fix code blocks - detect and set appropriate language
    def process_code_block(match):
        block_content = match.group(1) if match.group(1) else ""
        # Remove any internal code block markers
        block_content = re.sub(r'```[a-zA-Z0-9_+-]*\s*\n?', '', block_content)
        # Detect language if not explicitly specified
        if match.group(0).startswith('```') and len(match.group(0).split('\n')[0]) > 3:
            lang = match.group(0).split('\n')[0].replace('```', '')
        else:
            lang = detect_code_language(block_content)
        return f'```{lang}\n{block_content.strip()}\n```'

    # Process all code blocks
    content = re.sub(r'```(?:[a-zA-Z0-9_+-]*)\n((?:(?!```)[\s\S])*?)```', process_code_block, content)

    # Escape email addresses for MDX - replace @ with &#64;

    def _escape_email(match):
        email = match.group(1).replace('@', '&#64;')
        return f"&lt;{email}&gt;"

    content = re.sub(r'<([^>]+@[^>]+)>', _escape_email, content)

    # Clean up extra whitespace
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()

    # Create frontmatter
    frontmatter = f"""---
title: {title}
description: {description}
# This file is auto-generated from manpages. Do not edit manually.
# Source: {filename}
---

# {title}

"""

    return frontmatter + content


def get_output_filename(input_filename):
    """Generate output filename from input filename"""
    base = os.path.basename(input_filename)

    if base == 'ramalama.1.md':
        # Base ramalama command goes in commands directory
        return 'ramalama.mdx'
    if base.startswith('ramalama-') and base.endswith('.1.md'):
        # Command: ramalama-chat.1.md -> chat.mdx
        return base.replace('ramalama-', '').replace('.1.md', '.mdx')
    if base.startswith('ramalama-') and base.endswith('.7.md'):
        # Platform guide: ramalama-cuda.7.md -> cuda.mdx
        return base.replace('ramalama-', '').replace('.7.md', '.mdx')
    if base.endswith('.5.md'):
        # Config: ramalama.conf.5.md -> conf.mdx
        return base.replace('ramalama.', '').replace('.5.md', '.mdx')

    return base.replace('.md', '.mdx')


def clean_auto_generated_files(docsite_docs_dir):
    """Remove all auto-generated MDX files from previous runs"""
    print("Cleaning up auto-generated files from previous runs...")

    # Find all .mdx files recursively
    mdx_files = glob.glob(str(docsite_docs_dir / '**/*.mdx'), recursive=True)

    cleaned_count = 0
    for mdx_file in mdx_files:
        try:
            with open(mdx_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check if file has auto-generated marker
                if '# This file is auto-generated from manpages' in content:
                    os.remove(mdx_file)
                    cleaned_count += 1
                    print(f"  Removed: {mdx_file}")
        except Exception as e:
            print(f"  Warning: Could not process {mdx_file}: {e}")

    print(f"✅ Cleaned up {cleaned_count} auto-generated files")


def main():
    docs_dir = Path('../docs')
    docsite_docs_dir = Path('./docs')

    # Clean up auto-generated files from previous runs
    clean_auto_generated_files(docsite_docs_dir)

    # Find all manpage files
    manpage_files = glob.glob(str(docs_dir / '*.md'))
    manpage_files = [f for f in manpage_files if not f.endswith('README.md')]

    print(f"\nFound {len(manpage_files)} manpage files to convert")

    manpage_entries = []
    for input_file in manpage_files:
        filename = os.path.basename(input_file)
        output_filename = get_output_filename(filename)
        _, subdir = get_category_info(filename)
        relative_output_path = Path(subdir) / output_filename
        manpage_entries.append((input_file, filename, relative_output_path))

    output_map = {filename: relative_path for _, filename, relative_path in manpage_entries}

    for input_file, filename, relative_output_path in manpage_entries:
        print(f"Converting {filename}...")

        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        mdx_content = convert_markdown_to_mdx(content, filename, relative_output_path, output_map)

        output_dir = (docsite_docs_dir / relative_output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = docsite_docs_dir / relative_output_path

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(mdx_content)

        print(f"  -> {output_path}")

    print("\nConversion complete!")


if __name__ == '__main__':
    main()
