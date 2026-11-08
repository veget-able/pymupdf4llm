"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .original_grid_restoration import install
    install(runtime)
    runtime.installed_components.append('T20')
