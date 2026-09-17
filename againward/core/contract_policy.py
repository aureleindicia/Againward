"""Contract-derived technical permissions, not legal interpretation or a lifecycle.

The agent extracts only operational rules. A human reviews the exact extraction.
Raw agreements stay in contracts/; downstream code consumes this closed projection.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .workflow_paths import resolve_case_layout

SCHEMA = 'againward-contract-policy-v1'
POLICY_PATH = 'contracts/contract_policy.json'
REVIEW_PATH = 'contracts/contract_review.json'
PERMISSIONS = {
    'agreement_active', 'contract_signed', 'client_data_processing_allowed',
    'confidentiality_applies', 'derived_retention_authorized',
    'internal_rnd_use_authorized', 'benchmarking_use_authorized',
    'portfolio_use_authorized', 'client_quote_use_authorized',
}
FIELDS = PERMISSIONS | {
    'schema_version', 'contract_ref', 'effective_at', 'retention_policy_ref',
    'purge_after_utc', 'external_processing_constraints', 'source_refs',
    'review_status', 'ambiguity_codes', 'permitted_retained_paths',
}
PURPOSE_PERMISSIONS = {
    'INTERNAL_RND': 'internal_rnd_use_authorized',
    'BENCHMARKING': 'benchmarking_use_authorized',
    'PORTFOLIO': 'portfolio_use_authorized',
    'CLIENT_QUOTE': 'client_quote_use_authorized',
}


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError('CONTRACT_GATE: artefact contractuel absent ou invalide.') from exc
    if not isinstance(value, dict):
        raise ValueError('CONTRACT_GATE: objet structuré requis.')
    return value


def _instant(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError('CONTRACT_GATE: date ISO avec fuseau requise.') from exc
    if result.tzinfo is None:
        raise ValueError('CONTRACT_GATE: date sans fuseau refusée.')
    return result


def contract_policy_digest(policy):
    return hashlib.sha256(json.dumps(policy, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def _local_file(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('CONTRACT_GATE: référence locale relative requise.')
    path = root / relative
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)) or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('CONTRACT_GATE: source absente ou hors dossier.')
    return path


def contract_policy_template():
    return {'schema_version': SCHEMA, **dict.fromkeys(PERMISSIONS),
            'contract_ref': None, 'effective_at': None,
            'retention_policy_ref': 'privacy/retention_policy.json',
            'purge_after_utc': None, 'external_processing_constraints': None,
            'source_refs': [], 'review_status': 'EXTRACTED', 'ambiguity_codes': [],
            'permitted_retained_paths': []}


def validate_contract_policy(root, policy):
    """Validate extraction structure and source hashes; never infer permissions."""
    root = Path(root)
    if not isinstance(policy, dict) or set(policy) != FIELDS or policy.get('schema_version') != SCHEMA:
        raise ValueError('CONTRACT_GATE: contrat de policy fermé requis ; aucun contenu brut libre.')
    if any(policy[k] is not None and type(policy[k]) is not bool for k in PERMISSIONS):
        raise ValueError('CONTRACT_GATE: autorisations true / false / null uniquement.')
    if policy['review_status'] not in {'EXTRACTED', 'HUMAN_LEGAL_REVIEW_REQUIRED', 'REVIEWED'}:
        raise ValueError('CONTRACT_GATE: statut de revue inconnu.')
    for key in ('ambiguity_codes', 'external_processing_constraints'):
        values = policy[key]
        if key == 'external_processing_constraints' and values is None:
            continue
        if not isinstance(values, list) or any(not isinstance(x, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', x) for x in values):
            raise ValueError('CONTRACT_GATE: codes de contraintes/ambiguïtés requis, pas le contrat brut.')
    for key in ('effective_at', 'purge_after_utc'):
        if policy[key] is not None:
            _instant(policy[key])
    if policy['retention_policy_ref'] != 'privacy/retention_policy.json':
        raise ValueError('CONTRACT_GATE: réutiliser la rétention canonique.')
    refs = policy['source_refs']
    if not isinstance(refs, list) or not refs:
        raise ValueError('CONTRACT_GATE: provenance de l’extraction requise.')
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'} or not str(ref['path']).startswith('contracts/'):
            raise ValueError('CONTRACT_GATE: source contractuelle minimale path / sha256 requise.')
        if ref['path'] in {POLICY_PATH, REVIEW_PATH}:
            raise ValueError('CONTRACT_GATE: provenance circulaire refusée.')
        if hashlib.sha256(_local_file(root, ref['path']).read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('CONTRACT_GATE: source contractuelle modifiée.')
    if policy['contract_ref'] not in {r['path'] for r in refs}:
        raise ValueError('CONTRACT_GATE: accord applicable absent des sources.')
    retained = policy['permitted_retained_paths']
    if not isinstance(retained, list) or any(not isinstance(p, str) or Path(p).is_absolute() or '..' in Path(p).parts
            or p.endswith('/') or not p.startswith(('contracts/', 'billing/', 'outputs/')) for p in retained):
        raise ValueError('CONTRACT_GATE: rétention limitée à des fichiers explicitement autorisés.')
    if any(p.startswith('outputs/') and Path(p).suffix.lower() != '.pdf' for p in retained):
        raise ValueError('CONTRACT_GATE: seuls les livrables PDF peuvent être retenus dans outputs ; aucun learning Markdown libre.')
    return policy


def record_contract_policy(case_directory, policy, *, semantic_extraction, human_review=None):
    """Persist a human-supplied approval if present; never create an approval."""
    from .privacy import _atomic_json
    root = resolve_case_layout(case_directory)['case_root']
    validate_contract_policy(root, policy)
    if semantic_extraction != {'completed': True, 'extractor_role': 'CODEX'}:
        raise ValueError('CONTRACT_GATE: extraction sémantique Codex explicitement attestée requise.')
    if policy['ambiguity_codes'] or policy['external_processing_constraints'] is None:
        policy = {**policy, 'review_status': 'HUMAN_LEGAL_REVIEW_REQUIRED'}
    if human_review is not None:
        _validate_review(policy, human_review)
    # The review binds to the digest, so any later policy change invalidates it.
    authorization_ref = None
    if human_review is not None:
        authorization = {'policy': policy, 'human_review': human_review}
        authorization_ref = 'contracts/authorizations/' + contract_policy_digest(authorization) + '.json'
        path = root / authorization_ref
        if path.exists() and _read(path) != authorization:
            raise ValueError('CONTRACT_GATE: historique d’autorisation incohérent.')
        _atomic_json(path, authorization)
    _atomic_json(root / POLICY_PATH, policy)
    _atomic_json(root / 'contracts/contract_extraction.json', {
        'semantic_extraction': semantic_extraction, 'policy_sha256': contract_policy_digest(policy),
        'source_refs': policy['source_refs'], 'authorization_ref': authorization_ref, 'not_a_legal_opinion': True})
    if human_review is not None:
        _atomic_json(root / REVIEW_PATH, human_review)
    return {'policy_ref': POLICY_PATH, 'policy_sha256': contract_policy_digest(policy),
            'review_status': policy['review_status'], 'not_a_legal_opinion': True}


def _validate_review(policy, review):
    if (not isinstance(review, dict) or set(review) != {'approved', 'policy_sha256', 'reviewer_role',
            'reviewed_at_utc', 'external_processing_constraints_satisfied'}
            or review.get('approved') is not True or not isinstance(review.get('reviewer_role'), str)
            or not review['reviewer_role'].strip()
            or review.get('policy_sha256') != contract_policy_digest(policy)
            or review.get('external_processing_constraints_satisfied') is not True):
        raise ValueError('HUMAN_LEGAL_REVIEW_REQUIRED: approbation humaine exacte et contraintes vérifiées requises.')
    _instant(review['reviewed_at_utc'])
    if policy['review_status'] != 'REVIEWED' or policy['ambiguity_codes'] or policy['external_processing_constraints'] is None:
        raise ValueError('HUMAN_LEGAL_REVIEW_REQUIRED: ambiguïté non résolue.')


def reviewed_contract_policy(case_directory):
    root = resolve_case_layout(case_directory)['case_root']
    policy = validate_contract_policy(root, _read(root / POLICY_PATH))
    if policy['review_status']=='HUMAN_LEGAL_REVIEW_REQUIRED' or policy['ambiguity_codes'] or policy['external_processing_constraints'] is None:
        raise ValueError('HUMAN_LEGAL_REVIEW_REQUIRED: clause ou contrainte ambiguë.')
    extraction = _read(root / 'contracts/contract_extraction.json')
    if extraction.get('policy_sha256') != contract_policy_digest(policy) or extraction.get('semantic_extraction') != {'completed': True, 'extractor_role': 'CODEX'}:
        raise ValueError('CONTRACT_GATE: extraction absente ou périmée.')
    _validate_review(policy, _read(root / REVIEW_PATH))
    return policy


def assert_contract_permission(case_directory, *, operation='processing', purpose=None, now=None):
    if operation not in {'processing', 'staging', 'delivery', 'retention'}:
        raise ValueError('CONTRACT_GATE: opération inconnue.')
    from .privacy import privacy_requirement
    requirement = privacy_requirement(case_directory)
    if not requirement['required']:
        return None
    policy = reviewed_contract_policy(case_directory)
    if operation in {'processing', 'staging', 'delivery'}:
        retention_file = resolve_case_layout(case_directory)['case_root'] / 'privacy/retention_policy.json'
        if retention_file.is_file() and _read(retention_file).get('mission_closed') is True:
            raise ValueError('CONTRACT_GATE: mission close ; aucun nouveau traitement analytique.')
        if any(policy[k] is not True for k in ('agreement_active', 'client_data_processing_allowed', 'confidentiality_applies')):
            raise ValueError('CONTRACT_GATE: accord actif et traitement confidentiel explicitement autorisé requis.')
        instant = now or datetime.now(timezone.utc)
        if not _instant(policy['effective_at']) <= instant < _instant(policy['purge_after_utc']):
            raise ValueError('CONTRACT_GATE: période de traitement non applicable ou échue.')
    if operation == 'delivery':
        root = resolve_case_layout(case_directory)['case_root']
        manifest = _read(root / 'privacy/privacy_manifest.json')
        authorization_ref = manifest.get('contract_authorization_ref')
        if not isinstance(authorization_ref, str) or not authorization_ref.startswith('contracts/authorizations/'):
            raise ValueError('CONTRACT_GATE: autorisation historique du traitement non tracée.')
        authorization = _read(_local_file(root, authorization_ref))
        if Path(authorization_ref).stem != contract_policy_digest(authorization):
            raise ValueError('CONTRACT_GATE: autorisation historique altérée.')
        historic = validate_contract_policy(root, authorization['policy'])
        _validate_review(historic, authorization['human_review'])
        validated_at = _instant(manifest.get('validated_at_utc'))
        if (historic['client_data_processing_allowed'] is not True or historic['agreement_active'] is not True
                or not _instant(historic['effective_at']) <= validated_at < _instant(historic['purge_after_utc'])):
            raise ValueError('CONTRACT_GATE: traitement historique non autorisé.')
        retention = _read(root / policy['retention_policy_ref'])
        if retention.get('configured') is not True or retention.get('mission_closed') is True:
            raise ValueError('CONTRACT_GATE: rétention configurée et mission ouverte requises pour livraison.')
        validate_retention_authorization(case_directory, retention)
        if retention.get('contract_policy_sha256') != contract_policy_digest(policy):
            raise ValueError('CONTRACT_GATE: rétention non liée à la policy courante.')
    if purpose is not None:
        permission = PURPOSE_PERMISSIONS.get(purpose)
        if not permission or policy['derived_retention_authorized'] is not True or policy[permission] is not True:
            raise ValueError('CONTRACT_GATE: conservation et finalité secondaire non autorisées.')
    return policy


def inspect_contract_status(case_directory):
    from .privacy import privacy_requirement
    if not privacy_requirement(case_directory)['required']:
        return {'state': 'NOT_REQUIRED', 'allowed': True}
    try:
        policy = assert_contract_permission(case_directory)
        return {'state': 'CONTRACT_CLEARED', 'allowed': True, 'policy_ref': POLICY_PATH,
                'policy_sha256': contract_policy_digest(policy)}
    except ValueError as exc:
        return {'state': 'HUMAN_LEGAL_REVIEW_REQUIRED' if 'HUMAN_LEGAL_REVIEW_REQUIRED' in str(exc) else 'CONTRACT_BLOCKED',
                'allowed': False, 'reason': str(exc), 'policy_ref': POLICY_PATH}


def validate_retention_authorization(case_directory, retention):
    """Reuse retention_policy.json; contract rights remain an independent prerequisite."""
    from .privacy import privacy_requirement
    if not privacy_requirement(case_directory)['required']:
        return None
    policy = reviewed_contract_policy(case_directory)
    if _instant(retention.get('purge_after_utc')) != _instant(policy['purge_after_utc']):
        raise ValueError('CONTRACT_GATE: échéance de rétention différente de la policy revue.')
    if set(retention.get('retained_paths', [])) - set(policy['permitted_retained_paths']):
        raise ValueError('CONTRACT_GATE: fichier retenu sans autorisation contractuelle.')
    if retention.get('derived_retention_authorized') is True and policy['derived_retention_authorized'] is not True:
        raise ValueError('CONTRACT_GATE: dérivés non autorisés par le contrat.')
    return policy
