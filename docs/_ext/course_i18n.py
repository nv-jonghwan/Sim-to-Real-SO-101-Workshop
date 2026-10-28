"""Keep MyST table cells translatable and provide language navigation."""
from copy import deepcopy
from docutils import nodes
from sphinx.transforms import SphinxTransform

class TableMessageSources(SphinxTransform):
    # Locale runs at priority 20. MyST 4 table cells have rawsource but no source.
    default_priority = 19

    def apply(self, **kwargs):
        self.document["course_original_myst_slugs"] = deepcopy(
            self.env.metadata.get(self.env.docname, {}).get("myst_slugs", {})
        )
        for node in self.document.findall(nodes.TextElement):
            if node.source or not node.rawsource:
                continue
            parent = node.parent
            while parent is not None and not parent.source:
                parent = parent.parent
            if parent is not None:
                node.source = parent.source
                node.line = parent.line


class RestoreHeadingSlugs(SphinxTransform):
    # Locale reparses translated fragments; MyST must not replace the whole
    # document slug map with a fragment's translated headings.
    default_priority = 21

    def apply(self, **kwargs):
        original = self.document.attributes.pop("course_original_myst_slugs", {})
        if original:
            self.env.metadata[self.env.docname]["myst_slugs"] = original
            self.document.myst_slugs = original


def page_context(app, pagename, templatename, context, doctree):
    audience = 'event' if app.tags.has('event') else 'learner'
    korean = app.config.language == 'ko'
    # Both languages retain identical page names. Also works for genindex/search.
    context['course_language_href'] = ('../../../' if korean else '../../ko/') + audience + '/html/' + pagename + '.html'
    context['course_language_label'] = 'English' if korean else '한국어'


def setup(app):
    app.add_transform(TableMessageSources)
    app.add_transform(RestoreHeadingSlugs)
    app.connect('html-page-context', page_context)
    return {'version':'1.1', 'env_version':1, 'parallel_read_safe':True, 'parallel_write_safe':True}
