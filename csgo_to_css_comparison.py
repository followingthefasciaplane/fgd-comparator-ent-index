from valvefgd import FgdParse, Fgd, FgdEntity, FgdEntityProperty, FgdEntitySpawnflag, FgdEntityInput, FgdEntityOutput, FgdEditorData
import json
from typing import Dict, List, Any, Union
import io
from collections import defaultdict

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
        'new_entities': list(csgo_entity_names - css_entity_names),
        'removed_entities': list(css_entity_names - csgo_entity_names),
        'modified_entities': {},
        'editor_data_changes': compare_editor_data(css_fgd.editor_data, csgo_fgd.editor_data)
    }

    common_entities = css_entity_names & csgo_entity_names
    for entity_name in common_entities:
        # Retrieve entities by original casing if necessary
        css_entity = next(e for e in css_fgd.entities if e.name.lower() == entity_name)
        csgo_entity = next(e for e in csgo_fgd.entities if e.name.lower() == entity_name)
        entity_diff = compare_entity(css_entity, csgo_entity)
        if entity_diff:
            differences['modified_entities'][csgo_entity.name] = entity_diff

    return differences


def compare_editor_data(css_editor_data: List[FgdEditorData], csgo_editor_data: List[FgdEditorData]) -> Dict[str, Any]:
    def get_key(ed: FgdEditorData):
        return (ed.class_type, ed.name) if ed.name else (ed.class_type,)

    css_data = {get_key(ed): ed for ed in css_editor_data}
    csgo_data = {get_key(ed): ed for ed in csgo_editor_data}

    new = [csgo_data[key].to_dict() for key in csgo_data.keys() - css_data.keys()]
    removed = [css_data[key].to_dict() for key in css_data.keys() - csgo_data.keys()]
    modified = {
        key: {
            'css': css_data[key].data,
            'csgo': csgo_data[key].data
        }
        for key in css_data.keys() & csgo_data.keys()
        if css_data[key].data != csgo_data[key].data
    }

    return {
        'new': new,
        'removed': removed,
        'modified': modified
    }


def compare_entity(css_entity: FgdEntity, csgo_entity: FgdEntity) -> Dict[str, Any]:
    differences = {}

    if css_entity.class_type != csgo_entity.class_type:
        differences['class_type'] = {'css': css_entity.class_type, 'csgo': csgo_entity.class_type}

    if css_entity.description != csgo_entity.description:
        differences['description'] = {'css': css_entity.description, 'csgo': csgo_entity.description}

    # Sort definitions for order-insensitive comparison
    sorted_css_definitions = sorted(css_entity.definitions, key=lambda d: sorted(d.items()))
    sorted_csgo_definitions = sorted(csgo_entity.definitions, key=lambda d: sorted(d.items()))
    
    if sorted_css_definitions != sorted_csgo_definitions:
        differences['definitions'] = {'css': sorted_css_definitions, 'csgo': sorted_csgo_definitions}

    prop_diff = compare_properties(css_entity.properties, csgo_entity.properties)
    if prop_diff:
        differences['properties'] = prop_diff

    spawnflag_diff = compare_spawnflags(css_entity.spawnflags, csgo_entity.spawnflags)
    if spawnflag_diff:
        differences['spawnflags'] = spawnflag_diff

    input_diff = compare_io(css_entity.inputs, csgo_entity.inputs)
    if input_diff:
        differences['inputs'] = input_diff

    output_diff = compare_io(css_entity.outputs, csgo_entity.outputs)
    if output_diff:
        differences['outputs'] = output_diff

    return differences


def compare_properties(css_props: List[FgdEntityProperty], csgo_props: List[FgdEntityProperty]) -> Dict[str, Any]:
    if not css_props and not csgo_props:
        return None
    
    css_prop_dict = {prop.name.lower(): prop for prop in css_props or []}
    csgo_prop_dict = {prop.name.lower(): prop for prop in csgo_props or []}

    differences = {
        'new': list(set(csgo_prop_dict.keys()) - set(css_prop_dict.keys())),
        'removed': list(set(css_prop_dict.keys()) - set(csgo_prop_dict.keys())),
        'modified': {}
    }

    for prop_name in set(css_prop_dict.keys()) & set(csgo_prop_dict.keys()):
        css_prop = css_prop_dict[prop_name]
        csgo_prop = csgo_prop_dict[prop_name]
        prop_diff = compare_property(css_prop, csgo_prop)
        if prop_diff:
            differences['modified'][csgo_prop.name] = prop_diff  # Use original casing

    return differences if differences['new'] or differences['removed'] or differences['modified'] else None


def compare_property(css_prop: FgdEntityProperty, csgo_prop: FgdEntityProperty) -> Dict[str, Any]:
    differences = {}
    for attr in ['value_type', 'readonly', 'report', 'display_name', 'default_value', 'description']:
        css_value = getattr(css_prop, attr)
        csgo_value = getattr(csgo_prop, attr)
        if css_value != csgo_value:
            differences[attr] = {'css': css_value, 'csgo': csgo_value}

    # Handle the case where choices might be None
    if css_prop.choices is not None or csgo_prop.choices is not None:
        css_choices = sorted(
            [{'value': c.value, 'display_name': c.display_name} for c in (css_prop.choices or [])],
            key=lambda x: x['value']
        )
        csgo_choices = sorted(
            [{'value': c.value, 'display_name': c.display_name} for c in (csgo_prop.choices or [])],
            key=lambda x: x['value']
        )
        if css_choices != csgo_choices:
            differences['choices'] = {
                'css': css_choices,
                'csgo': csgo_choices
            }

    return differences if differences else None

def compare_spawnflags(css_flags: List[FgdEntitySpawnflag], csgo_flags: List[FgdEntitySpawnflag]) -> Dict[str, Any]:
    css_flag_dict = defaultdict(list)
    for flag in css_flags:
        try:
            flag_value = int(flag.value)
        except ValueError:
            print(f"Invalid flag value in CS:S FGD: {flag.value}")
            continue
        css_flag_dict[flag_value].append(flag)

    csgo_flag_dict = defaultdict(list)
    for flag in csgo_flags:
        try:
            flag_value = int(flag.value)
        except ValueError:
            print(f"Invalid flag value in CS:GO FGD: {flag.value}")
            continue
        csgo_flag_dict[flag_value].append(flag)

    differences = {
        'new': [f"{value} ({flag.display_name})" for value in set(csgo_flag_dict.keys()) - set(css_flag_dict.keys()) for flag in csgo_flag_dict[value]],
        'removed': [f"{value} ({flag.display_name})" for value in set(css_flag_dict.keys()) - set(csgo_flag_dict.keys()) for flag in css_flag_dict[value]],
        'modified': {}
    }

    for flag_value in set(css_flag_dict.keys()) & set(csgo_flag_dict.keys()):
        css_flag_list = css_flag_dict[flag_value]
        csgo_flag_list = csgo_flag_dict[flag_value]

        for css_flag, csgo_flag in zip(css_flag_list, csgo_flag_list):
            flag_diff = compare_spawnflag(css_flag, csgo_flag)
            if flag_diff:
                key = f"{flag_value} ({csgo_flag.display_name})"
                differences['modified'][key] = flag_diff

    # Clean up empty categories
    differences = {k: v for k, v in differences.items() if v}

    return differences if differences else None


def compare_spawnflag(css_flag: FgdEntitySpawnflag, csgo_flag: FgdEntitySpawnflag) -> Dict[str, Any]:
    differences = {}
    # List of attributes to compare; ensure these are actual attributes of FgdEntitySpawnflag
    attributes_to_compare = ['display_name', 'default_value']

    for attr in attributes_to_compare:
        css_value = getattr(css_flag, attr, None)
        csgo_value = getattr(csgo_flag, attr, None)
        if css_value != csgo_value:
            differences[attr] = {'css': css_value, 'csgo': csgo_value}

    return differences if differences else None

def compare_io(css_io: List[Union[FgdEntityInput, FgdEntityOutput]], csgo_io: List[Union[FgdEntityInput, FgdEntityOutput]]) -> Dict[str, Any]:
    css_io_dict = {io.name.lower(): io for io in css_io}
    csgo_io_dict = {io.name.lower(): io for io in csgo_io}

    differences = {
        'new': list(set(csgo_io_dict.keys()) - set(css_io_dict.keys())),
        'removed': list(set(css_io_dict.keys()) - set(csgo_io_dict.keys())),
        'modified': {}
    }

    for io_name in set(css_io_dict.keys()) & set(csgo_io_dict.keys()):
        css_io_item = css_io_dict[io_name]
        csgo_io_item = csgo_io_dict[io_name]
        io_diff = compare_io_item(css_io_item, csgo_io_item)
        if io_diff:
            differences['modified'][csgo_io_item.name] = io_diff  # Use original casing

    return differences if differences['new'] or differences['removed'] or differences['modified'] else None


def compare_io_item(css_io: Union[FgdEntityInput, FgdEntityOutput], csgo_io: Union[FgdEntityInput, FgdEntityOutput]) -> Dict[str, Any]:
    if type(css_io) != type(csgo_io):
        return {'type': {'css': type(css_io).__name__, 'csgo': type(csgo_io).__name__}}

    differences = {}
    for attr in ['value_type', 'description']:
        css_value = getattr(css_io, attr, None)
        csgo_value = getattr(csgo_io, attr, None)
        if css_value != csgo_value:
            differences[attr] = {'css': css_value, 'csgo': csgo_value}

    return differences if differences else None


def main():
    css_fgd = load_fgd('cstrike/cstrike.fgd')
    csgo_fgd = load_fgd('csgo/csgo.fgd')
    
    differences = compare_fgds(css_fgd, csgo_fgd)
    
    with io.open('cs_fgd_differences_summary.json', 'w', encoding='utf-8') as f:
        json.dump(differences, f, indent=2, ensure_ascii=False)
    
    print("Comprehensive differences summary has been written to cs_fgd_differences_summary.json")

    # Generate a text summary
    with io.open('cs_fgd_differences_summary.txt', 'w', encoding='utf-8') as f:
        f.write("Summary of differences between CS:S and CS:GO FGDs\n\n")
        f.write(f"New entities in CS:GO: {len(differences['new_entities'])}\n")
        f.write(f"Removed entities in CS:GO: {len(differences['removed_entities'])}\n")
        f.write(f"Modified entities: {len(differences['modified_entities'])}\n")
        f.write(f"Editor data changes: {len(differences['editor_data_changes']['new']) + len(differences['editor_data_changes']['removed']) + len(differences['editor_data_changes']['modified'])}\n\n")

        f.write("Top 10 modified entities with the most changes:\n")
        sorted_entities = sorted(differences['modified_entities'].items(), 
                                 key=lambda x: sum(len(changes) for changes in x[1].values() if isinstance(changes, dict)),
                                 reverse=True)
        for entity_name, changes in sorted_entities[:10]:
            f.write(f"\n{entity_name}:\n")
            for change_type, change_data in changes.items():
                if isinstance(change_data, dict) and all(key in change_data for key in ['new', 'removed', 'modified']):
                    f.write(f"  {change_type.capitalize()}:\n")
                    f.write(f"    New: {len(change_data['new'])}\n")
                    f.write(f"    Removed: {len(change_data['removed'])}\n")
                    f.write(f"    Modified: {len(change_data['modified'])}\n")
                else:
                    f.write(f"  {change_type.capitalize()} changed\n")

    print("Summary text has been written to cs_fgd_differences_summary.txt")

if __name__ == "__main__":
    main()