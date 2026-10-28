# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


import importlib.metadata
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "_ext"))

from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective


project = 'Train an SO-101 Robot From Sim-to-Real With NVIDIA Isaac'
copyright = '2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved'
author = 'NVIDIA'
release = importlib.metadata.version("learning_path")
print(release)

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'course_i18n',
    'interactive_i18n',
    'sphinx.ext.intersphinx',
    'myst_parser',
    'sphinx_design',
    'sphinx_copybutton',
    'sphinx_nvlearning',
]

templates_path = ['_templates']
exclude_patterns = ['_build', '_includes/**', 'locale/**', '_ext/**']
locale_dirs = ['locale']
gettext_compact = False
myst_enable_extensions = ['colon_fence', 'html_image', 'attrs_inline', 'attrs_block', 'substitution']
myst_title_to_header = True
myst_number_code_blocks = ['python', 'py', 'usda', 'usd']
myst_links_external_new_tab = True
myst_heading_anchors = 3

event_build = tags.has("event")
if event_build:
    exclude_patterns.append('02-how-to-take-this-course.md')
else:
    exclude_patterns.append('2026-10-28-seoul-preparation.md')

_seoul_toctree = """:::{toctree}
:caption: AI Day Seoul 2026
:maxdepth: 1

{preparation}
seoul-workshop-schedule
:::"""

_overview_toctree = """:::{toctree}
:caption: Overview
:maxdepth: 2
:hidden:

01-overview
{how_to}
04-lerobot
:::"""
_setup_toctree = """:::{toctree}
:caption: {caption}
:maxdepth: 2
:hidden:

05-building-workspace
06-get-the-code
:::"""

myst_substitutions = {
    "seoul_lessons": _seoul_toctree.replace("{preparation}", "2026-10-28-seoul-preparation" if event_build else ""),
    "overview_lessons": _overview_toctree.replace("{how_to}", "" if event_build else "02-how-to-take-this-course"),
    "setup_lessons": "" if event_build else _setup_toctree.replace("{caption}", "Build Your Robot Lab"),
    "video_width": "400",
    "learning_path_repo_path":"`~/Sim-to-Real-SO-101-Workshop/`",
    "learning_path_repo_cd_path": "```\ncd ~/Sim-to-Real-SO-101-Workshop\n```",
    "sim_only_dataset": "sreetz-nv/so101_teleop_vials_left",
    "sim_and_real_dataset": "sreetz-nv/so101_teleop_vials_merged",
    "sim_and_real_dataset_repo_id": "sreetz-nv/so101_teleop_vials_merged",
    "sim_and_real_dataset_repo_root": "/home/ubuntu/sim-to-real-learning-path/datasets/so101_teleop_vials_merged",
    "sim_and_real_dataset_task_name": "Pick up the vial and place it in the rack",
}


# TODO: Remove the two following parameters when the theme is fixed
toc_object_entries_show_parents = 'hide'
maximum_signature_line_length = 70



html_theme = 'nvidia_sphinx_theme'
html_static_path = ['_static']
html_css_files = ['groot-hyperparameters.css', 'image-comparison.css', 'course-banners.css', 'model-cards.css', 'module-types.css', 'sidebar-toggle.css', 'seoul-schedule.css']
html_js_files = [
    ('sidebar-toggle.js', {'defer': 'defer'}),
    ('interactive-diagram-embed.js', {'defer': 'defer'}),
    ('groot-hyperparameters.js', {'defer': 'defer'}),
    ('image-comparison.js', {'defer': 'defer'}),
]
html_theme_options = {
    "article_header_start": ["sidebar-toggle.html", "breadcrumbs", "course-language.html"],
     "icon_links": [
        {
            "name": "Survey",
            "url": "https://forms.gle/WC82m74fnxTrB8et9",
            "icon": "fa-solid fa-comment",
            "type": "fontawesome",
        }
    ],
    "extra_head": {
        """
    <script src="https://assets.adobedtm.com/5d4962a43b79/c1061d2c5e7b/launch-191c2462b890.min.js" ></script>
    """
    },
    "extra_footer": {
        """
    <script type="text/javascript">if (typeof _satellite !== "undefined") {_satellite.pageBottom();}</script>
    """
    },
}


if event_build:
    html_theme_options["extra_footer"].add(
        '<small><a href="workshop-preparation.html">Instructor setup</a></small>'
    )


class Audience(SphinxDirective):
    """Parse content only for the selected course audience, including headings."""

    has_content = True
    required_arguments = 1

    def run(self):
        audience = self.arguments[0]
        if audience not in {"learner", "event"}:
            raise self.error("audience must be 'learner' or 'event'")
        selected = "event" if self.env.app.tags.has("event") else "learner"
        if audience != selected:
            return []
        return self.parse_content_to_nodes(allow_section_headings=True)


def remove_presenter_page_from_learner(app, exception):
    """Keep the presenter page out of incremental learner HTML builds."""
    if exception is not None or app.tags.has("event") or app.builder.format != "html":
        return
    name = "2026-10-28-seoul-preparation"
    for path in (
        Path(app.outdir) / f"{name}.html",
        Path(app.outdir) / "_sources" / f"{name}.md.txt",
        Path(app.doctreedir) / f"{name}.doctree",
    ):
        path.unlink(missing_ok=True)


def setup(app: Sphinx):
    app.add_directive("audience", Audience)
    app.connect("build-finished", remove_presenter_page_from_learner)
