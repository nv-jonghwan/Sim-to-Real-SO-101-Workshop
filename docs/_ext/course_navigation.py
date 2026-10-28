"""Use Sphinx toctree navigation for the end-of-page course handoff."""


def page_context(app, pagename, templatename, context, doctree):
    if doctree is None or not context.get("next"):
        return
    context["course_next_heading"] = "다음 단계" if app.config.language == "ko" else "What's Next?"
    context["course_next_label"] = "목차 순서에 따라 다음 페이지로 이동하세요:" if app.config.language == "ko" else "Continue to the next page in the table of contents:"
    context["body"] += app.builder.templates.render("course-next.html", context)


def setup(app):
    app.connect("html-page-context", page_context)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
