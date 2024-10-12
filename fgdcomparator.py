import json
from datetime import datetime
from typing import Dict, List, Any, Union
import io
from valvefgd import FgdParse, Fgd, FgdEntity, FgdEntityProperty, FgdEntitySpawnflag, FgdEntityInput, FgdEntityOutput, FgdEditorData

def load_fgd(file_path: str) -> Fgd:
    try:
        return FgdParse(file_path)
    except Exception as e:
        print(f"Error loading FGD file '{file_path}': {e}")
        raise

def compare_fgds(css_fgd: Fgd, csgo_fgd: Fgd) -> Dict[str, Any]:
    css_entity_names = set(e.name.lower() for e in css_fgd.entities)
    csgo_entity_names = set(e.name.lower() for e in csgo_fgd.entities)

    differences = {
        'metadata': {
            'css_version': 'Counter-Strike: Source',
            'csgo_version': 'Counter-Strike: Global Offensive',
            'comparison_date': datetime.now().isoformat(),
        },
        'new_entities': sorted(list(csgo_entity_names - css_entity_names)),
        'removed_entities': sorted(list(css_entity_names - csgo_entity_names)),
        'modified_entities': {},
        'backward_porting_issues': [],
    }

    common_entities = css_entity_names & csgo_entity_names
    for entity_name in common_entities:
        css_entity = next(e for e in css_fgd.entities if e.name.lower() == entity_name)
        csgo_entity = next(e for e in csgo_fgd.entities if e.name.lower() == entity_name)
        entity_diff = compare_entity(css_entity, csgo_entity)
        if entity_diff:
            differences['modified_entities'][csgo_entity.name] = entity_diff

    # Identify potential backward porting issues
    for entity_name in csgo_entity_names:
        csgo_entity = next(e for e in csgo_fgd.entities if e.name.lower() == entity_name)
        css_entity = next((e for e in css_fgd.entities if e.name.lower() == entity_name), None)
        
        if not css_entity:
            differences['backward_porting_issues'].append({
                'entity': entity_name,
                'issue': 'New entity in CSGO, not present in CSS',
                'severity': 'High'
            })
        else:
            csgo_only_properties = set(p.name for p in csgo_entity.properties) - set(p.name for p in css_entity.properties)
            for prop in csgo_only_properties:
                differences['backward_porting_issues'].append({
                    'entity': entity_name,
                    'property': prop,
                    'issue': 'Property exists in CSGO but not in CSS',
                    'severity': 'Medium'
                })

    return differences

def compare_entity(css_entity: FgdEntity, csgo_entity: FgdEntity) -> Dict[str, Any]:
    differences = {}

    if css_entity.class_type != csgo_entity.class_type:
        differences['class_type'] = {'css': css_entity.class_type, 'csgo': csgo_entity.class_type}

    if css_entity.description != csgo_entity.description:
        differences['description'] = {
            'css': css_entity.description,
            'csgo': csgo_entity.description,
        }

    definitions_diff = compare_definitions(css_entity.definitions, csgo_entity.definitions)
    if definitions_diff:
        differences['definitions'] = definitions_diff

    prop_diff = compare_properties(css_entity.properties, csgo_entity.properties)
    if prop_diff:
        differences['properties'] = prop_diff

    spawnflag_diff = compare_spawnflags(css_entity.spawnflags, csgo_entity.spawnflags)
    if spawnflag_diff:
        differences['spawnflags'] = spawnflag_diff

    input_diff = compare_io(css_entity.inputs, csgo_entity.inputs, 'input')
    if input_diff:
        differences['inputs'] = input_diff

    output_diff = compare_io(css_entity.outputs, csgo_entity.outputs, 'output')
    if output_diff:
        differences['outputs'] = output_diff

    if differences:
        differences['changes_summary'] = {
            'properties': count_changes(prop_diff),
            'inputs': count_changes(input_diff),
            'outputs': count_changes(output_diff),
            'spawnflags': count_changes(spawnflag_diff),
        }
        differences['backward_porting_complexity'] = calculate_porting_complexity(differences)

    return differences

def compare_definitions(css_defs: List[Dict[str, Any]], csgo_defs: List[Dict[str, Any]]) -> Dict[str, Any]:
    css_bases = [d for d in css_defs if d.get('name') == 'base']
    csgo_bases = [d for d in csgo_defs if d.get('name') == 'base']
    
    if css_bases != csgo_bases:
        return {
            'css': css_bases,
            'csgo': csgo_bases,
            'changes': {
                'added': [b for b in csgo_bases if b not in css_bases],
                'removed': [b for b in css_bases if b not in csgo_bases],
            }
        }
    return None

def compare_properties(css_props: List[FgdEntityProperty], csgo_props: List[FgdEntityProperty]) -> Dict[str, Any]:
    css_prop_dict = {prop.name.lower(): prop for prop in css_props}
    csgo_prop_dict = {prop.name.lower(): prop for prop in csgo_props}

    differences = {
        'new': sorted(list(set(csgo_prop_dict.keys()) - set(css_prop_dict.keys()))),
        'removed': sorted(list(set(css_prop_dict.keys()) - set(csgo_prop_dict.keys()))),
        'modified': {}
    }

    for prop_name in set(css_prop_dict.keys()) & set(csgo_prop_dict.keys()):
        css_prop = css_prop_dict[prop_name]
        csgo_prop = csgo_prop_dict[prop_name]
        prop_diff = compare_property(css_prop, csgo_prop)
        if prop_diff:
            differences['modified'][csgo_prop.name] = prop_diff

    return differences if differences['new'] or differences['removed'] or differences['modified'] else None

def compare_property(css_prop: FgdEntityProperty, csgo_prop: FgdEntityProperty) -> Dict[str, Any]:
    differences = {}
    for attr in ['value_type', 'readonly', 'report', 'display_name', 'default_value', 'description']:
        css_value = getattr(css_prop, attr)
        csgo_value = getattr(csgo_prop, attr)
        if css_value != csgo_value:
            differences[attr] = {'css': css_value, 'csgo': csgo_value}

    if css_prop.choices != csgo_prop.choices:
        differences['choices'] = {
            'css': [c.schema for c in css_prop.choices] if css_prop.choices else None,
            'csgo': [c.schema for c in csgo_prop.choices] if csgo_prop.choices else None
        }

    return differences if differences else None

def compare_spawnflags(css_flags: List[FgdEntitySpawnflag], csgo_flags: List[FgdEntitySpawnflag]) -> Dict[str, Any]:
    css_flag_dict = {int(flag.value): flag for flag in css_flags}
    csgo_flag_dict = {int(flag.value): flag for flag in csgo_flags}

    differences = {
        'new': [],
        'removed': [],
        'modified': {}
    }

    all_values = set(css_flag_dict.keys()) | set(csgo_flag_dict.keys())

    for value in all_values:
        css_flag = css_flag_dict.get(value)
        csgo_flag = csgo_flag_dict.get(value)

        if css_flag and not csgo_flag:
            differences['removed'].append(css_flag.schema)
        elif csgo_flag and not css_flag:
            differences['new'].append(csgo_flag.schema)
        elif css_flag and csgo_flag:
            flag_diff = compare_spawnflag(css_flag, csgo_flag)
            if flag_diff:
                differences['modified'][str(value)] = flag_diff

    return differences if any(differences.values()) else None

def compare_spawnflag(css_flag: FgdEntitySpawnflag, csgo_flag: FgdEntitySpawnflag) -> Dict[str, Any]:
    differences = {}
    
    if css_flag.display_name != csgo_flag.display_name:
        differences['display_name'] = {
            'css': css_flag.display_name,
            'csgo': csgo_flag.display_name
        }
    
    if css_flag.default_value != csgo_flag.default_value:
        differences['default_value'] = {
            'css': css_flag.default_value,
            'csgo': csgo_flag.default_value
        }

    return differences if differences else None

def compare_io(css_io: List[Union[FgdEntityInput, FgdEntityOutput]], csgo_io: List[Union[FgdEntityInput, FgdEntityOutput]], io_type: str) -> Dict[str, Any]:
    css_io_dict = {io.name.lower(): io for io in css_io}
    csgo_io_dict = {io.name.lower(): io for io in csgo_io}

    differences = {
        'new': sorted(list(set(csgo_io_dict.keys()) - set(css_io_dict.keys()))),
        'removed': sorted(list(set(css_io_dict.keys()) - set(csgo_io_dict.keys()))),
        'modified': {}
    }

    for io_name in set(css_io_dict.keys()) & set(csgo_io_dict.keys()):
        css_io_item = css_io_dict[io_name]
        csgo_io_item = csgo_io_dict[io_name]
        io_diff = compare_io_item(css_io_item, csgo_io_item)
        if io_diff:
            differences['modified'][csgo_io_item.name] = io_diff

    return differences if any(differences.values()) else None

def compare_io_item(css_io: Union[FgdEntityInput, FgdEntityOutput], csgo_io: Union[FgdEntityInput, FgdEntityOutput]) -> Dict[str, Any]:
    differences = {}
    for attr in ['value_type', 'description']:
        css_value = getattr(css_io, attr, None)
        csgo_value = getattr(csgo_io, attr, None)
        if css_value != csgo_value:
            differences[attr] = {'css': css_value, 'csgo': csgo_value}

    return differences if differences else None

def count_changes(diff: Dict[str, Any]) -> Dict[str, int]:
    if not diff:
        return {'new': 0, 'removed': 0, 'modified': 0}
    return {
        'new': len(diff.get('new', [])),
        'removed': len(diff.get('removed', [])),
        'modified': len(diff.get('modified', {}))
    }

def calculate_porting_complexity(differences: Dict[str, Any]) -> str:
    # This is a more nuanced complexity calculation
    complexity_score = 0
    
    if 'class_type' in differences:
        complexity_score += 3
    
    if 'definitions' in differences:
        complexity_score += len(differences['definitions']['changes']['added']) * 2
        complexity_score += len(differences['definitions']['changes']['removed']) * 2
    
    changes_summary = differences['changes_summary']
    
    complexity_score += changes_summary['properties']['new'] * 2
    complexity_score += changes_summary['properties']['removed'] * 2
    complexity_score += changes_summary['properties']['modified']
    
    complexity_score += changes_summary['inputs']['new'] * 1.5
    complexity_score += changes_summary['inputs']['removed'] * 1.5
    complexity_score += changes_summary['inputs']['modified'] * 0.5
    
    complexity_score += changes_summary['outputs']['new'] * 1.5
    complexity_score += changes_summary['outputs']['removed'] * 1.5
    complexity_score += changes_summary['outputs']['modified'] * 0.5
    
    complexity_score += changes_summary['spawnflags']['new']
    complexity_score += changes_summary['spawnflags']['removed']
    complexity_score += changes_summary['spawnflags']['modified'] * 0.5

    if complexity_score > 20:
        return 'High'
    elif complexity_score > 10:
        return 'Medium'
    else:
        return 'Low'

def main():
    css_fgd = load_fgd('cstrike/cstrike.fgd')
    csgo_fgd = load_fgd('csgo/csgo.fgd')
    
    differences = compare_fgds(css_fgd, csgo_fgd)
    
    with io.open('cs_fgd_differences.json', 'w', encoding='utf-8') as f:
        json.dump(differences, f, indent=2, ensure_ascii=False)
    
    print("Comprehensive differences have been written to cs_fgd_differences.json")

    # Generate a text summary
    with io.open('cs_fgd_differences_summary.txt', 'w', encoding='utf-8') as f:
        f.write("Summary of differences between CS:S and CS:GO FGDs\n\n")
        f.write(f"Comparison date: {differences['metadata']['comparison_date']}\n")
        f.write(f"CSS Version: {differences['metadata']['css_version']}\n")
        f.write(f"CSGO Version: {differences['metadata']['csgo_version']}\n\n")
        f.write(f"New entities in CS:GO: {len(differences['new_entities'])}\n")
        f.write(f"Removed entities in CS:GO: {len(differences['removed_entities'])}\n")
        f.write(f"Modified entities: {len(differences['modified_entities'])}\n")
        f.write(f"Backward porting issues: {len(differences['backward_porting_issues'])}\n\n")

        f.write("Top 10 modified entities with the most changes:\n")
        sorted_entities = sorted(differences['modified_entities'].items(), 
                                 key=lambda x: sum(sum(v.values()) for v in x[1]['changes_summary'].values()),
                                 reverse=True)
        for entity_name, changes in sorted_entities[:10]:
            f.write(f"\n{entity_name} (Porting Complexity: {changes['backward_porting_complexity']}):\n")
            for change_type, change_data in changes['changes_summary'].items():
                f.write(f"  {change_type.capitalize()}:\n")
                f.write(f"    New: {change_data['new']}\n")
                f.write(f"    Removed: {change_data['removed']}\n")
                f.write(f"    Modified: {change_data['modified']}\n")
            
            if 'definitions' in changes:
                f.write("  Definitions changed\n")
            if 'class_type' in changes:
                f.write(f"  Class type changed from {changes['class_type']['css']} to {changes['class_type']['csgo']}\n")
            if 'description' in changes:
                f.write("  Description changed\n")

        f.write("\nTop backward porting issues:\n")
        for issue in differences['backward_porting_issues'][:10]:
            f.write(f"  Entity: {issue['entity']}\n")
            f.write(f"  Issue: {issue['issue']}\n")
            f.write(f"  Severity: {issue['severity']}\n")
            if 'property' in issue:
                f.write(f"  Property: {issue['property']}\n")
            f.write("\n")

    print("Summary text has been written to cs_fgd_differences_summary.txt")

if __name__ == "__main__":
    main()