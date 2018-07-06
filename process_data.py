"""Data processing pipeline.

To be run from /Volumes/disks/jonas/freshStart/modeling
"""


import subprocess as sp
from constants import lines
from var_vis import var_vis
from tools import icr, already_exists, uvaver


def pipe(commands):
    """Translate a set of arguments into a CASA command."""
    call_string = '\n'.join([command if type(command) is str else '\n'.join(command) for command in commands])

    print('Piping the following commands to CASA:\n')
    print(call_string)
    sp.call(['casa', '-c', call_string])

    # clean up .log files that casa poops out
    sp.call('rm -rf *.log', shell=True)


def casa_sequence(mol, split_range, raw_data_path,
                 final_data_path, remake_all=False):
    """Cvel, split, and export as uvf the original cont-sub'ed .ms.

    Args:
        - mol:
        - split_range:
        - raw_data_path:
        - final_data_path:
        - remake_all (bool): if True, remove delete all pre-existing files.
    """
    if remake_all is True:
        sp.call(['rm -rf {}.*'.format(final_data_path)])

    if already_exists(final_data_path + '_cvel.ms') is False:
        pipe(["cvel(",
              "vis='{}calibrated-{}.ms.contsub',".format(raw_data_path, mol),
              "outputvis='{}_cvel.ms',".format(final_data_path),
              "field='OrionField4',",
              "restfreq='{}GHz',".format(lines[mol]['restfreq']),
              "outframe='LSRK')"
              ])

    if already_exists(final_data_path + '_split.ms') is False:
        spw = '*:' + str(split_range[0]) + '~' + str(split_range[1])
        pipe(["split(",
              "vis='{}_cvel.ms',".format(final_data_path),
              "outputvis='{}_split.ms',".format(final_data_path),
              "spw='{}',".format(spw),
              "datacolumn='data',",
              "keepflags=False)"
              ])

    if already_exists(final_data_path + '_exportuvfits.uvf') is False:
        pipe(["exportuvfits(",
              "vis='{}_split.ms',".format(final_data_path),
              "fitsfile='{}_exportuvfits.uvf')".format(final_data_path)
              ])


def find_split_cutoffs(mol, other_restfreq=0):
    """Find the indices of the 50 channels around the restfreq.

    chan_dir, chan0, nchans, chanstep from
    listobs(vis='mol.ms', field='OrionField4')
    """
    chan_dir = lines[mol]['chan_dir']
    chan0 = lines[mol]['chan0']
    restfreq = lines[mol]['restfreq']

    # ALl in GHz
    nchans = 3840
    chanstep = chan_dir * 0.000488281
    freqs = [chan0 + chanstep*i for i in range(nchans)]

    # Using these two different restfreqs yields locs of 1908 vs 1932. Weird.
    if other_restfreq != 0:
        restfreq = other_restfreq

    # Find the index of the restfreq channel
    loc = 0
    min_diff = 1
    for i in range(len(freqs)):
        diff = abs(freqs[i] - restfreq)
        if diff < min_diff:
            min_diff = diff
            loc = i

    split_range = [loc - 25, loc + 25]
    return split_range


def run_full_pipeline(mol):
    """Run the whole thing.

    Not sure if it'll automatically wait for var_vis?
    The Process:
        - casa_sequence():
            - cvel the cont-sub'ed dataset from v2434_original_data to here.
            - split out the 50 channels around restfreq
            - convert that .ms to a .uvf
        - var_vis(): pull in that .uvf, add variances, resulting in another uvf
        - convert that to a vis
        - icr that vis to get a cm
        - cm to fits; now we have mol.{{uvf, vis, fits, cm}}
        - delete the clutter files: _split, _cvel, _exportuvfits, bm, cl, mp
    """
    # Paths to the data
    jonas = '/Volumes/disks/jonas/'
    raw_data_path = jonas + 'raw_data/'
    final_data_path = jonas + 'freshStart/modeling/data/' + mol + '/' + mol

    b_min = lines[mol]['baseline_cutoff']
    split_range = find_split_cutoffs(mol)

    print "Split range is ", str(split_range[0]), str(split_range[1])
    print "Now processing data...."
    casa_sequence(mol, split_range, raw_data_path, final_data_path)
    print "Finished casa_sequence()\n\n"

    print "Running varvis....\n\n"
    if already_exists(final_data_path + '.uvf') is False:
        # Note that var_vis just returns mol.uvf
        var_vis(final_data_path)

    print "Finished varvis; converting uvf to vis now....\n\n"
    if already_exists(final_data_path + '.vis') is False:
        sp.call(['fits',
                 'op=uvin',
                 'in={}.uvf'.format(final_data_path),
                 'out={}.vis'.format(final_data_path)
                 ])

    print "Cutting out baselines below", b_min
    uvaver(final_data_path)

    print "Convolving data to get image, converting output to .fits\n\n"
    if already_exists(final_data_path + '.cm') is False:
        icr(final_data_path)

    print "Deleting the junk process files...\n\n"
    # Clear out the bad stuff.
    sp.call(['rm -rf',
             '{}.bm'.format(final_data_path),
             '{}.cl'.format(final_data_path),
             '{}.mp'.format(final_data_path),
             '{}_cvel.*'.format(final_data_path),
             '{}_split.*'.format(final_data_path),
             '{}_exportuvfits.*'.format(final_data_path),
             'casa*.log'],
            shell=True)

    with open('README.txt', 'w') as f:
        readme = 'These visibilities were cut at' + b_min
    print "All done!"


# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description='Clean CASA measurement sets')
#     parser.add_argument('vis', help='path(s) of visibilities to be cleaned')
#     parser.add_argument('-concat', help='output path of concatenation')
#     parser.add_argument('rms', help='either float or CASA region used to get rms with imstat')
#     parser.add_argument('mask', help='clean mask file')
#     args=parser.parse_args()
#
#     vis_list = args.vis.split(',')
#     if args.concat:
#         concatenate(vis_list, args.concat)
#         clean(args.concat, args.rms, args.mask)
#     else:
#         for vis in vis_list: clean(vis, rms, mask)

    # if len(vis_list) > 1:
    #     concat(vis_list,)
    #
    # clean(vis_list, rms, mask)