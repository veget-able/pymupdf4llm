"""Finder-scoped metadata produced with placements, consumed by R6 transfer.

No predicted labels are cached here. Source keys belong to immutable native
CellContent/CellSource producers. Geometry belongs to the complete current cell
shape; tags are deliberately excluded from material and included in the existing
live decision fingerprint. Every new finder starts an independent lifetime.
"""
from collections import Counter,defaultdict
from contextlib import contextmanager
from dataclasses import replace
import time


class PreparedCorrespondence:
    def __init__(self):
        from . import header_material as base
        self.base=base;self.stats=defaultdict(int);self.scope=None
        self.native_material=base.material;self.native_roles=base.source_roles
        self.native_geometry=base.span_geometry

    @contextmanager
    def lifetime(self):
        previous=self.scope
        self.scope=dict(sources={},contents={},grids={},semantic_grids={},metadata={},roles={},geometry={},prefix={},pairs={})
        try:yield
        finally:self.scope=previous

    def content(self,cell):
        content=cell.source_content
        if content is None:
            if cell.text.strip():raise ValueError('text_without_source_proof')
            return ()
        if cell.text!=content.text:raise ValueError('Cell text changed after production without transferring source content')
        key=id(content);saved=self.scope['contents'].get(key)
        if saved is not None:
            assert saved[0] is content;self.stats['content_hits']+=1;return saved[1]
        keys=[]
        for source in content.sources:
            # CellSource objects can be rebuilt while referring to the exact
            # same native word. Compare all frozen fields and producer identity;
            # the (collection,index) address alone is not sufficient evidence.
            address=(source.kind,id(source.collection),int(source.index))
            bucket=self.scope['sources'].setdefault(address,[])
            record=next((entry for entry in bucket if entry[0].collection is source.collection and entry[0]==source),None)
            if record is None:
                record=(source,self.base.source_key(source));bucket.append(record)
                self.stats['source_key_producer_calls']+=1
            else:self.stats['source_key_hits']+=1
            keys.append(record[1])
        keys=tuple(keys)
        if cell.text.strip() and not keys:raise ValueError('text_without_source_proof')
        self.scope['contents'][key]=(content,keys)
        self.stats['content_producer_calls']+=1
        return keys

    def material(self,grid):
        if self.scope is None:return self.native_material(grid)
        self.stats['material_requests']+=1;started=time.perf_counter_ns()
        try:
            shape=tuple(tuple((tuple(c.bbox) if c.bbox is not None else None,c.text,int(c.colspan),int(c.rowspan),id(c.source_content)) for c in row) for row in grid)
            saved=self.scope['grids'].get(shape)
            if saved is not None:self.stats['material_hits']+=1;return saved
            # Equivalent immutable contents from strict/non-strict native
            # placements share the material view, not their mutable SpanCells.
            values=tuple(tuple(self.content(c) for c in row) for row in grid)
            semantic=tuple(tuple((*item[:4],keys) for item,keys in zip(row,keys_row)) for row,keys_row in zip(shape,values))
            saved=self.scope['semantic_grids'].get(semantic)
            if saved is not None:
                self.scope['grids'][shape]=saved;self.stats['semantic_material_hits']+=1;return saved
            rows=[];counts=Counter();empty={};row_sources=[]
            for ri,row in enumerate(grid):
                cells=[];sources=set()
                for c,keys in zip(row,values[ri]):
                    counts.update(keys);sources.update(keys)
                    cells.append(self.base.Cell(tuple(c.bbox) if c.bbox is not None else None,c.text,int(c.colspan),int(c.rowspan),keys,c.source_content))
                rows.append(tuple(cells));row_sources.append(frozenset(sources))
                if not any(c.sources or c.text.strip() for c in cells):empty[ri]=tuple((c.bbox,c.colspan,c.rowspan) for c in cells)
            data=self.base.Material(tuple(rows),counts,empty)
            self.scope['grids'][shape]=data
            self.scope['semantic_grids'][semantic]=data
            self.scope['metadata'][id(data)]=(data,tuple(row_sources))
            self.stats['material_producer_calls']+=1
            return data
        finally:self.stats['material_ns']+=time.perf_counter_ns()-started

    def prepare(self,grid):
        # Missing source proof declines transfer, never changes native extraction.
        try:return self.material(grid)
        except ValueError:self.stats['unprovable_producer_grids']+=1;return None

    def roles(self,data,region):
        if self.scope is None:return self.native_roles(data,region)
        key=(id(data),region.top_header_rows,tuple(region.section_header_rows))
        if key in self.scope['roles']:self.stats['role_index_hits']+=1;return self.scope['roles'][key]
        result=self.native_roles(data,region);self.scope['roles'][key]=result
        self.stats['role_index_producer_calls']+=1
        return result

    def geometry(self,data,occupancy):
        if self.scope is None:return self.native_geometry(data,occupancy)
        if id(data) in self.scope['geometry']:self.stats['geometry_hits']+=1;return self.scope['geometry'][id(data)]
        result=self.native_geometry(data,occupancy);self.scope['geometry'][id(data)]=result
        self.stats['geometry_producer_calls']+=1
        return result

    def prefix(self,data,depth,norm):
        key=(id(data),depth)
        cache=self.scope['prefix'] if self.scope is not None else {}
        if key in cache:self.stats['prefix_hits']+=1;return cache[key]
        result=tuple(tuple((c.bbox,norm(c.text),c.colspan,c.rowspan,frozenset(Counter(c.sources).items())) for c in row) for row in data.rows[:depth+2])
        cache[key]=result;self.stats['prefix_producer_calls']+=1;return result

    def correspondence(self,old,new,region,spans,occupancy):
        if not old.data.counts:return None,'empty_source_set'
        if old.data.counts!=new.counts:return None,'material_multiset_changed'
        self.stats['correspondence_requests']+=1
        # Repeated clones of prepared placements share their row/source index.
        if self.scope is not None:
            record=self.scope['metadata'][id(new)];assert record[0] is new
            row_sources=record[1];self.stats['prepared_row_index_consumers']+=1
        else:row_sources=[frozenset(k for c in row for k in c.sources) for row in new.rows]
        roles=[]
        for ri,keys in enumerate(row_sources):
            votes={old.roles[key] for key in keys}
            if len(votes)>1:return None,'header_body_or_section_source_mix'
            if votes:roles.append(next(iter(votes)));continue
            matches={((oi<old.region.top_header_rows),(oi in old.region.section_header_rows)) for oi,shape in old.data.empty_rows.items() if shape==new.empty_rows.get(ri)}
            if len(matches)!=1:return None,'empty_row_correspondence_unknown'
            roles.append(next(iter(matches)))
        depth=max((ri+1 for ri,role in enumerate(roles) if role[0]),default=0)
        if any(not role[0] for role in roles[:depth]):return None,'header_role_not_a_prefix'
        sections=tuple(ri for ri,role in enumerate(roles) if role[1])
        from .header_semantic_order import posterior_sections
        if sections!=posterior_sections(new.rows,depth):return None,'post_model_section_context_changed'
        try:
            self.geometry(new,occupancy)
            # Same immutable prepared geometry already proves equal layouts.
            # Crossing the H/body boundary still needs its native validation.
            pair=(id(old.data),old.region.top_header_rows,id(new),depth)
            cache=self.scope['pairs'] if self.scope is not None else {}
            if pair not in cache:
                bounds=spans._span_clustered_boundaries([x for data in (old.data,new) for row in data.rows for c in row if c.bbox is not None for x in (c.bbox[0],c.bbox[2])])
                cache[pair]=(self.base.header_layout(old.data,old.region.top_header_rows,bounds,spans)==self.base.header_layout(new,depth,bounds,spans))
                self.stats['header_layout_producer_calls']+=1
            else:self.stats['header_layout_hits']+=1
            if not cache[pair]:return None,'header_cell_or_column_correspondence_changed'
        except ValueError as error:return None,str(error)
        return replace(region,top_header_rows=depth,section_header_rows=sections),'verified_source_and_header_geometry'
