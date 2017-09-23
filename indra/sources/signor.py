from __future__ import absolute_import, print_function, unicode_literals
from builtins import dict, str
import logging
from collections import namedtuple, Counter, defaultdict

from indra.statements import *
from indra.util import read_unicode_csv
from indra.databases import hgnc_client, uniprot_client

logger = logging.getLogger('signor')


_signor_fields = [
    'ENTITYA',
    'TYPEA',
    'IDA',
    'DATABASEA',
    'ENTITYB',
    'TYPEB',
    'IDB',
    'DATABASEB',
    'EFFECT',
    'MECHANISM',
    'RESIDUE',
    'SEQUENCE',
    'TAX_ID',
    'CELL_DATA',
    'TISSUE_DATA',
    'MODULATOR_COMPLEX',
    'TARGET_COMPLEX',
    'MODIFICATIONA',
    'MODASEQ',
    'MODIFICATIONB',
    'MODBSEQ',
    'PMID',
    'DIRECT',
    'NOTES',
    'ANNOTATOR',
    'SENTENCE',
    'SIGNOR_ID',
]


_type_db_map = {
    ('antibody', None): None,
    ('protein', 'UNIPROT'): 'UP',
    ('complex', 'SIGNOR'): 'SIGNOR',
    ('proteinfamily', 'SIGNOR'): 'SIGNOR',
    ('smallmolecule', 'SIGNOR'): 'PUBCHEM',
    ('pathway', None): None,
    ('phenotype', 'SIGNOR'): 'SIGNOR',
    ('stimulus', 'SIGNOR'): 'SIGNOR',
    ('chemical', 'PUBCHEM'): 'PUBCHEM',
}

_mechanism_map = {
    'catalytic activity': None, # Conversion
    'oxidoreductase activity': None,
    'transcriptional activation': None, # IncreaseAmount by tscript
    'transcriptional repression': None, # DecreaseAmount by tscript
    'Farnesylation': Farnesylation,
    'gtpase-activating protein': Gap,
    'deacetylation': Deacetylation,
    'demethylation': Demethylation,
    'dephosphorylation': Dephosphorylation,
    'destabilization': DecreaseAmount,
    'guanine nucleotide exchange factor': Gef,
    'acetylation': Acetylation,
    'binding': Complex,
    'cleavage': None, # Important!
    'desumoylation': Desumoylation,
    'deubiquitination': Deubiquitination,
    'glycosylation': Glycosylation,
    'hydroxylation': Hydroxylation,
    'neddylation': None, # Neddylation,
    'chemical activation': Activation,
    'chemical inhibition': Inhibition,
    'trimethylation': Methylation,
    'ubiquitination': Ubiquitination,
    'post transcriptional regulation': None,
    'relocalization': Translocation,
    'small molecule catalysis': None,
    's-nitrosylation': None,
    'transcriptional regulation': RegulateAmount, # Subject has tscript activity
    'translation regulation': None,
    'tyrosination': None,
    'lipidation': None,
    'oxidation': None,
    'methylation': Methylation,
    'palmitoylation': Palmitoylation,
    'phosphorylation': Phosphorylation,
    'stabilization': IncreaseAmount,
    'sumoylation': Sumoylation
}

SignorRow = namedtuple('SignorRow', _signor_fields)


class SignorProcessor(object):
    """Processor for Signor dataset, available at http://signor.uniroma2.it.

    See publication:

    Perfetto et al., "SIGNOR: a database of causal relationships between
    biological entities," Nucleic Acids Research, Volume 44, Issue D1, 4
    January 2016, Pages D548–D554. https://doi.org/10.1093/nar/gkv1048

    Parameters
    ----------
    signor_csv : str
        Path to SIGNOR CSV file.
    delimiter : str
        Field delimiter for CSV file. Defaults to semicolon ';'.
    """
    def __init__(self, signor_csv, delimiter=';'):
        # Get generator over the CSV file
        data_iter = read_unicode_csv(signor_csv, delimiter=';')
        # Skip the header row
        next(data_iter)
        # Process into a list of SignorRow namedtuples
        self._data = [SignorRow(*r) for r in data_iter]
        self.statements = []

    def make_model(self):
        mechs = []
        mech_map = defaultdict(list)
        for row in self._data:
            #self.statements.append(self._process_row(row))
            key = (row.EFFECT, row.MECHANISM)
            mechs.append(key)
            mech_map[key].append(row)
        mech_ctr = Counter(mechs)
        mech_ctr = sorted(mech_ctr.items(), key=lambda x: x[1], reverse=True)
        return (mech_ctr, mech_map)

    @staticmethod
    def _get_agent(ent_name, ent_type, id, database):
        gnd_type = _type_db_map[(ent_type, database)]
        if gnd_type == 'UP':
            up_id = id
            db_refs = {'UP': up_id}
            name = uniprot_client.get_gene_name(up_id)
            hgnc_id = hgnc_client.get_hgnc_id(name)
            if hgnc_id:
                db_refs['HGNC'] = hgnc_id
        # Other possible groundings are PUBCHEM and SIGNOR
        elif gnd_type is not None:
            assert database in ('PUBCHEM', 'SIGNOR')
            db_refs = {database: id}
            name = ent_name
        # If no grounding, include as an untyped/ungrounded node
        else:
            name = ent_name
            db_refs = {}
        return Agent(name, db_refs=db_refs)

    #@staticmethod(agent_a, agent_b, mechanism, effect,
    @staticmethod
    def _get_evidence(row):
        # Get epistemics (direct/indirect)
        epistemics = {}
        epistemics['direct'] = True if row.DIRECT == 'YES' else False
        # Get annotations
        _n = lambda s: s if s else None
        annotations = {
                'SEQUENCE': _n(row.SEQUENCE),
                'TAX_ID': _n(row.TAX_ID),
                'CELL_DATA': _n(row.CELL_DATA),
                'TISSUE_DATA': _n(row.TISSUE_DATA),
                'MODULATOR_COMPLEX': _n(row.MODULATOR_COMPLEX),
                'TARGET_COMPLEX': _n(row.TARGET_COMPLEX),
                'MODIFICATIONA': _n(row.MODIFICATIONA),
                'MODASEQ': _n(row.MODASEQ),
                'MODIFICATIONB': _n(row.MODIFICATIONB),
                'MODBSEQ': _n(row.MODBSEQ),
                'NOTES': _n(row.NOTES),
                'ANNOTATOR': _n(row.ANNOTATOR)}
        return Evidence(source_api='SIGNOR', source_id=row.SIGNOR_ID,
                        pmid=row.PMID, text=row.SENTENCE,
                        epistemics=epistemics, annotations=annotations)


    @staticmethod
    def _process_row(row):
        agent_a = _get_agent(row.ENTITYA, row.TYPEA, row.IDA, row.DATABASEA)
        agent_b = _get_agent(row.ENTITYB, row.TYPEB, row.IDB, row.DATABASEB)
        
