"""Dependency-free validator for the workspace manifest's supported vocabulary."""
import re


def errors(value, schema, definitions=None, location='$'):
    definitions = definitions or schema
    if '$ref' in schema:
        target = definitions
        for part in schema['$ref'].removeprefix('#/').split('/'):
            target = target[part]
        return errors(value, target, definitions, location)
    result = []
    kinds = schema.get('type', [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    types = {'object': dict, 'array': list, 'string': str, 'integer': int, 'number': (float, int),
             'boolean': bool, 'null': type(None)}
    if kinds and not any(isinstance(value, types[k]) and not (k in ('integer', 'number') and isinstance(value, bool)) for k in kinds):
        return [location + ':type']
    if 'const' in schema and value != schema['const']:
        result.append(location + ':const')
    if 'enum' in schema and value not in schema['enum']:
        result.append(location + ':enum')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get('minimum', float('-inf')):
            result.append(location + ':minimum')
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or 'pattern' in schema and re.search(schema['pattern'], value) is None:
            result.append(location + ':string')
        if schema.get('format') == 'date-time':
            from datetime import datetime
            try:
                if datetime.fromisoformat(value).tzinfo is None:
                    raise ValueError('timezone required')
            except ValueError:
                result.append(location + ':date-time')
    if isinstance(value, dict):
        result += [location + ':missing:' + k for k in schema.get('required', []) if k not in value]
        if len(value) < schema.get('minProperties', 0):
            result.append(location + ':minProperties')
        properties = schema.get('properties', {})
        for key, item in value.items():
            rule = properties.get(key, schema.get('additionalProperties', True))
            if rule is False:
                result.append(location + ':extra:' + key)
            elif isinstance(rule, dict):
                result.extend(errors(item, rule, definitions, location + '.' + key))
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            result.append(location + ':minItems')
        for i, item in enumerate(value):
            result.extend(errors(item, schema.get('items', {}), definitions, f'{location}[{i}]'))
    return result
