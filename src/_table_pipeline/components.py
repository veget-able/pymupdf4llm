"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .header_band_split import install
    install(runtime)
    runtime.installed_components.append('T09')
