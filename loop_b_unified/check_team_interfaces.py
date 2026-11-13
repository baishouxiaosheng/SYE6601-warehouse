"""Read-only integration inventory. This is not a business Checker."""
import argparse
import json
from pathlib import Path

if __package__:
    from .raw_evidence import REGISTRY
else:
    from raw_evidence import REGISTRY

PROPOSED = {'MONITORING_SYSTEM': 'INCIDENT_DB', 'TICKET_SYSTEM': 'TICKET_DB'}


def audit(team_root):
    root = Path(team_root).resolve()
    rules = json.loads((root / 'base_rules_registry.json').read_text(encoding='utf-8-sig'))
    schema = json.loads((root / 'GraphProposal_Schema.json').read_text(encoding='utf-8-sig'))
    sources = set()
    node_types = set()
    expressions = []
    for rule in rules:
        spec = rule.get('dynamic_extraction_spec', {})
        for check in spec.get('mandatory_base_checks', []):
            if check.get('target_source'):
                sources.add(check['target_source'])
        for obligation in spec.get('runtime_obligations_to_extract', []):
            sources.update(obligation.get('target_sources', []))
            if obligation.get('node_type'):
                node_types.add(obligation['node_type'])
            expressions.append(obligation.get('condition_expression', ''))
    routing = []
    for source in sorted(sources):
        if source in REGISTRY:
            state, candidate = 'NAME_MATCH_ONLY', source
        elif source in PROPOSED:
            state, candidate = 'NEEDS_OWNER_CONFIRMATION', PROPOSED[source]
        else:
            state, candidate = 'NOT_IMPLEMENTED', None
        routing.append({'requested_source': source, 'state': state,
                        'candidate_provider_source': candidate, 'alias_enabled': False})
    props = schema['properties']['graph_proposal']['properties']
    enum = props['nodes']['items']['properties']['type']['enum']
    locator_type = props['nodes']['items']['properties']['source_locator']['properties']['locator']['type']
    graph_version_type = props['graph_version']['type']
    task_required = schema['properties']['task']['required']
    tool_required = ['task_id', 'run_id', 'customer_id', 'incident_id', 'event_time']
    unresolved = []
    for row in routing:
        if row['state'] != 'NAME_MATCH_ONLY':
            unresolved.append({'kind': row['state'], 'source': row['requested_source']})
    missing_task = sorted(set(tool_required) - set(task_required))
    if missing_task:
        unresolved.append({'kind': 'QUERY_FIELDS_NOT_REQUIRED_BY_PROPOSAL', 'fields': missing_task,
                           'owner': 'Loop A: ensure values before querying'})
    if locator_type != 'object':
        unresolved.append({'kind': 'LOCATOR_REPRESENTATION', 'proposal': locator_type,
                           'tool': 'object: start/end/unit', 'owner': 'Evidence chain'})
    if graph_version_type != 'integer':
        unresolved.append({'kind': 'DIFFERENT_STAGE_VERSION_CONTRACT', 'proposal': graph_version_type,
                           'terminal_snapshot': 'integer', 'owner': 'Loop A / evidence chain'})
    unlisted = sorted(node_types - set(enum))
    if unlisted:
        unresolved.append({'kind': 'PROPOSAL_NODE_TYPE_NOT_LISTED', 'types': unlisted,
                           'owner': 'Evidence chain / rule owner'})
    docs = json.loads((Path(__file__).resolve().parent / 'runtime_data' / 'documents.json').read_text(encoding='utf-8-sig'))
    rows = [row for doc in docs.values() for row in doc.get('records', [])]
    identity_fields = [f for f in ('customer_tier', 'plan_type') if not any(f in row for row in rows)]
    if identity_fields:
        unresolved.append({'kind': 'IDENTITY_MATERIAL_NOT_PROVIDED', 'fields': identity_fields,
                           'owner': 'Rule/data owner, then Loop B'})
    if any('planned_maintenance_minutes' in expr for expr in expressions):
        unresolved.append({'kind': 'MAINTENANCE_CALCULATION_NEEDS_SIGNOFF',
                           'detail': 'planned is not excluded; overlap intervals and subtraction policy need confirmation',
                           'owner': 'Rule owner / Checker / Loop B raw data'})
    controller = (root / 'dynamic_evidence' / 'controller.py').is_file()
    if not controller:
        unresolved.append({'kind': 'TEAM_CONTROLLER_NOT_AT_EXPECTED_PATH',
                           'expected': 'dynamic_evidence/controller.py', 'owner': 'Loop A / team lead'})
    return {'report_type': 'engineering_interface_inventory',
            'assessment': 'UNRESOLVED' if unresolved else 'NO_LISTED_DIFFERENCES',
            'business_acceptance': False, 'aliases_enabled': False,
            'scope_note': 'Name matches do not establish semantic or business compatibility. No business decisions made.',
            'current_module_path': 'loop_b_unified', 'source_inventory': routing,
            'controller_at_expected_path': controller, 'unresolved': unresolved,
            'manual_review': ['Contract thresholds and scope/version priority must be signed off',
                              'Loop A must provide an audited terminal snapshot, not only a GraphProposal']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--team-root', required=True)
    parser.add_argument('--output')
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    report = audit(args.team_root)
    output = Path(args.output) if args.output else Path(__file__).resolve().parent / 'raw_outputs' / 'interface_alignment.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Assessment:', report['assessment'])
    print('Unresolved items:', len(report['unresolved']))
    print('Report:', output)
    if args.strict and report['unresolved']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
