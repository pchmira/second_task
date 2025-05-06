import xml.etree.ElementTree as ET
import json
import uuid
from collections import defaultdict
import os


def parse_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    classes = {}
    aggregations = []

    for class_elem in root.findall('Class'):
        class_name = class_elem.get('name')
        is_root = class_elem.get('isRoot') == 'true'
        documentation = class_elem.get('documentation', '')

        attributes = []
        for attr in class_elem.findall('Attribute'):
            attributes.append({
                'name': attr.get('name'),
                'type': attr.get('type')
            })

        classes[class_name] = {
            'isRoot': is_root,
            'documentation': documentation,
            'attributes': attributes,
            'children': []
        }

    for agg in root.findall('Aggregation'):
        source = agg.get('source')
        target = agg.get('target')
        source_multiplicity = agg.get('sourceMultiplicity')
        target_multiplicity = agg.get('targetMultiplicity')

        aggregations.append({
            'source': source,
            'target': target,
            'sourceMultiplicity': source_multiplicity,
            'targetMultiplicity': target_multiplicity
        })

        if source in classes and target in classes:
            classes[target]['children'].append({
                'name': source,
                'multiplicity': source_multiplicity
            })

    return classes, aggregations


def generate_config_xml(classes):
    def build_xml_element(class_name, indent=0):
        xml = []
        class_data = classes[class_name]

        xml.append('  ' * indent + f'<{class_name}>')

        for attr in class_data['attributes']:
            xml.append('  ' * (indent + 1) + f'<{attr["name"]}>{attr["type"]}</{attr["name"]}>')

        for child in class_data['children']:
            xml.extend(build_xml_element(child['name'], indent + 1))

        xml.append('  ' * indent + f'</{class_name}>')
        return xml

    root_class = next(c for c, data in classes.items() if data['isRoot'])

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.extend(build_xml_element(root_class))

    return '\n'.join(xml_lines)


def generate_meta_json(classes, aggregations):
    meta = []

    for class_name, class_data in classes.items():
        multiplicity = {'min': '0', 'max': '*'}

        for agg in aggregations:
            if agg['source'] == class_name:
                source_mult = agg['sourceMultiplicity']
                if '..' in source_mult:
                    min_val, max_val = source_mult.split('..')
                    multiplicity['min'] = min_val
                    multiplicity['max'] = max_val
                else:
                    multiplicity['min'] = multiplicity['max'] = source_mult

        parameters = []
        for attr in class_data['attributes']:
            parameters.append({
                'name': attr['name'],
                'type': attr['type']
            })

        for child in class_data['children']:
            parameters.append({
                'name': child['name'],
                'type': 'class'
            })

        meta_entry = {
            'class': class_name,
            'documentation': class_data['documentation'],
            'isRoot': class_data['isRoot'],
            'parameters': parameters
        }

        if not class_data['isRoot']:
            meta_entry['min'] = multiplicity['min']
            meta_entry['max'] = multiplicity['max']

        meta.append(meta_entry)

    return json.dumps(meta, indent=4)


def generate_delta_json(config, patched_config):
    delta = {
        'additions': [],
        'deletions': [],
        'updates': []
    }

    for key, value in patched_config.items():
        if key not in config:
            delta['additions'].append({
                'key': key,
                'value': value
            })

    for key in config:
        if key not in patched_config:
            delta['deletions'].append(key)

    for key in config:
        if key in patched_config and config[key] != patched_config[key]:
            delta['updates'].append({
                'key': key,
                'from': config[key],
                'to': patched_config[key]
            })

    return json.dumps(delta, indent=4)


def generate_res_patched_config(config, delta_json):
    delta = json.loads(delta_json)
    result = config.copy()

    for key in delta['deletions']:
        result.pop(key, None)

    for update in delta['updates']:
        result[update['key']] = update['to']

    for addition in delta['additions']:
        result[addition['key']] = addition['value']

    return json.dumps(result, indent=4)


def main():
    os.makedirs('out', exist_ok=True)

    classes, aggregations = parse_xml('impulse_test_input.xml')

    config_xml = generate_config_xml(classes)
    with open(os.path.join('out', 'config.xml'), 'w') as f:
        f.write(config_xml)

    meta_json = generate_meta_json(classes, aggregations)
    with open(os.path.join('out', 'meta.json'), 'w') as f:
        f.write(meta_json)

    with open('config.json', 'r') as f:
        config = json.load(f)
    with open('patched_config.json', 'r') as f:
        patched_config = json.load(f)

    delta_json = generate_delta_json(config, patched_config)
    with open(os.path.join('out', 'delta.json'), 'w') as f:
        f.write(delta_json)

    res_patched_config = generate_res_patched_config(config, delta_json)
    with open(os.path.join('out', 'res_patched_config.json'), 'w') as f:
        f.write(res_patched_config)


if __name__ == '__main__':
    main()