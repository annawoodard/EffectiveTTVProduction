'''
to start a factory:
nohup work_queue_factory -T condor -M lobster_$USER.*ttV.*xsecs -d all -o /tmp/${USER}_lobster_ttV_xsecs.debug -C $(readlink -f xsec_factory.t3.json) >& /tmp/${USER}_lobster_ttV_xsec.log &
'''
import datetime
import glob
import os
import json

import numpy as np
import tempdir

from lobster import cmssw
from lobster.core import *

version = 'ttV/42'
base = os.path.dirname(os.path.abspath(__file__))
release = base[:base.find('/src')]

coefficients = ['c2B', 'c2G', 'c2W', 'c3G', 'c3W', 'c6', 'cA', 'cB', 'cG', 'cH', 'cHB', 'cHL', 'cHQ', 'cHW', 'cHd', 'cHe', 'cHu', 'cHud', 'cT', 'cWW', 'cd', 'cdB', 'cdG', 'cdW', 'cl', 'clB', 'clW', 'cpHL', 'cpHQ', 'cu', 'cuB', 'cuG', 'cuW', 'tc3G', 'tc3W', 'tcA', 'tcG', 'tcHB', 'tcHW']
coefficients = ['cHu', 'cu', 'cuW', 'cuB']
processes = [x.replace('slim_process_cards/', '').replace('.dat', '') for x in glob.glob('slim_process_cards/*.dat')]
processes = ['ttZ', 'ttH', 'ttW']

storage = StorageConfiguration(
    output=[
        "hdfs://eddie.crc.nd.edu:19000/store/user/$USER/" + version,
        # "file:///hadoop/store/user/$USER/" + version,
        "root://deepthought.crc.nd.edu//store/user/$USER/" + version,
        "srm://T3_US_NotreDame/store/user/$USER/" + version,
        "gsiftp://T3_US_NotreDame/store/user/$USER/" + version,
        # "chirp://eddie.crc.nd.edu:9094/store/user/$USER/" + version,
    ],
    input=[
        "root://deepthought.crc.nd.edu//store/user/$USER/{}/".format(version),
    ],
    disable_input_streaming=True
)

bounds_cat = Category(
    name='bounds',
    cores=1,
    memory=1000,
    disk=1500
)

xsecs_cat = Category(
    name='cross_sections',
    cores=1,
    memory=1000,
    disk=1500
)

# FIXME add Zgammastar?
# convergence of the loop expansion requires c < (4 * pi)^2
# see section 7 in https://arxiv.org/pdf/1205.4231.pdf
cutoff = (4 * np.pi) ** 2

workflows = []
for coefficient in coefficients:
    bounds = Workflow(
            label='bounds_{coefficient}'.format(coefficient=coefficient),
            dataset=EmptyDataset(number_of_tasks=1),
            category=bounds_cat,
            sandbox=cmssw.Sandbox(release=release),
            command='python bounds.py {gridpack} {mg} {inp} {outp} {cores} {events} {low} {high} {scale} {threshold} {constraints} {coefficient}'.format(
                gridpack='/cvmfs/cms.cern.ch/phys_generator/gridpacks/slc6_amd64_gcc481/13TeV/madgraph/V5_2.3.2.2/ttZ01j_5f_MLM/v1/ttZ01j_5f_MLM_tarball.tar.xz',
                mg='MG5_aMC_v2_3_3.third_gen.tar.gz',
                inp='mgbasedir/models/sm/restrict_no_b_mass.dat',
                outp='models/HEL_UFO/restrict_no_b_mass.dat',
                cores=6,
                events=50000,
                low=-1. * cutoff,
                high=cutoff,
                scale=5,
                threshold=1,
                constraints=' '.join(['{p}.dat'.format(p=p) for p in ['ttH', 'ttZ', 'ttW']]),
                coefficient=coefficient),
            extra_inputs=['{}/gen_jpeg-pl'.format(base), tempdir.__file__, '{}/MG5_aMC_v2_3_3.third_gen.tar.gz'.format(base), '{}/bounds.py'.format(base)] + ['{b}/slim_process_cards/{p}.dat'.format(b=base, p=p) for p in ['ttH', 'ttZ', 'ttW']],
            outputs=['bounds.npy']
        )

    workflows.append(bounds)
    workflows.append(Workflow(
                label='cross_sections_{}'.format(coefficient),
                dataset=ParentDataset(
                    parent=bounds,
                    units_per_task=1
                    ),
                category=xsecs_cat,
                sandbox=cmssw.Sandbox(release=release),
                command='python cross_sections.py {points} {cores} {events}'.format(
                    points=30,
                    cores=6,
                    events=50000),
                # unique_arguments=['{p}.dat {point}'.format(p=p, point=point) for p in processes for point in range(31)],
                unique_arguments=['{p}.dat'.format(p=p) for p in processes],
                outputs=['cross_sections.npy'],
                merge_command='python merge.py',
                merge_size='2G',
                extra_inputs=['{}/gen_jpeg-pl'.format(base), '{}/MG5_aMC_v2_3_3.third_gen.tar.gz'.format(base), tempdir.__file__, '{}/cross_sections.py'.format(base), '{}/merge.py'.format(base)] + ['{b}/slim_process_cards/{p}.dat'.format(b=base, p=p) for p in processes]
            )
        )

    # for process in processes:
    #     workflows.append(Workflow(
    #             label='diagrams_{process}_{coefficient}'.format(process=process, coefficient=coefficient),
    #             dataset=EmptyDataset(number_of_tasks=1),
    #             category=processing,
    #             sandbox=cmssw.Sandbox(release=release),
    #             command='python diagrams.py {gridpack} {mg} {inp} {outp} {cores} {events} {coefficient} {process}'.format(
    #                 gridpack='/cvmfs/cms.cern.ch/phys_generator/gridpacks/slc6_amd64_gcc481/13TeV/madgraph/V5_2.3.2.2/ttZ01j_5f_MLM/v1/ttZ01j_5f_MLM_tarball.tar.xz',
    #                 mg='MG5_aMC_v2_3_3.third_gen.tar.gz',
    #                 inp='mgbasedir/models/sm/restrict_no_b_mass.dat',
    #                 outp='models/HEL_UFO/restrict_no_b_mass.dat',
    #                 cores=6,
    #                 events=50000,
    #                 coefficient=coefficient,
    #                 process='{process}.dat'.format(process=process)),
    #             extra_inputs=['{}/gen_jpeg-pl'.format(base), tempdir.__file__, '{}/MG5_aMC_v2_3_3.third_gen.tar.gz'.format(base), '{b}/slim_process_cards/{p}.dat'.format(b=base, p=process), '{}/diagrams.py'.format(base)],
    #             outputs=['diagrams.tar.xz']
    #         )
    #     )


config = Config(
    label=str(version).replace('/', '_') + '_xsecs',
    workdir='/tmpscratch/users/$USER/' + version,
    plotdir='~/www/lobster/' + version,
    storage=storage,
    workflows=workflows,
    # advanced=AdvancedOptions(log_level=1, abort_multiplier=100000, dashboard=False, email="awoodard@nd.edu")
    advanced=AdvancedOptions(log_level=1, abort_multiplier=100000, email="awoodard@nd.edu")
)
