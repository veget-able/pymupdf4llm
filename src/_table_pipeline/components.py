"""Explicit assembly of the integrated, feature-owned consumers."""

def configure(runtime):
    from .native_union_policy import install as install_native_union_policy
    install_native_union_policy(runtime)
    runtime.installed_components.append('T04')
    from .independent_union import install as install_independent_union
    install_independent_union(runtime)
    runtime.installed_components.append('T05')
    from .union_split_coherence import install as install_union_split_coherence
    install_union_split_coherence(runtime)
    runtime.installed_components.append('T06')
    from .header_band_split import install as install_header_band_split
    install_header_band_split(runtime)
    runtime.installed_components.append('T09')
    from .header_provider import install as install_header_provider
    install_header_provider(runtime)
    runtime.installed_components.append('T11~T14')
    from .header_row_policy import install as install_header_row_policy
    install_header_row_policy(runtime)
    runtime.installed_components.append('T15')
    from .header_span_policy import install as install_header_span_policy
    install_header_span_policy(runtime)
    runtime.installed_components.append('T18')
