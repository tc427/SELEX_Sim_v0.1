#! /usr/bin/env python
# -*- coding: UTF8 -*-

import argparse
import os.path
import sys
import random

import numpy as np

from Aptamers import Aptamers
from Selection import Selection
from Distance import Distance
from Amplification import Amplification
from Mutation import Mutation
import utils

# Fetch experiment parameters from the settings file
import configparser


def main_sim(settings_file, postprocess_only):
    settings = configparser.ConfigParser({"initial_samples": "100000",
                                          "random_seed": "0",
                                          "img_format": "pdf",
                                          "pcr_bias": "0.1"},
                                         inline_comment_prefixes=(';',))
    settings.read(settings_file)

    if not settings.has_option("selectionparams", "initial_samples"):
        print("No initial samples defined, using default")

    aptamerType = settings.get('general', 'selex_type')
    aptamerNum = settings.getint('general', 'aptamer_mode')
    aptamerSeq = settings.get('general', 'reference_aptamer')
    seqLength = settings.getint('general', 'sequence_length')
    rng_seed = settings.getint('general', 'random_seed')
    roundNum = settings.getint('general', 'number_of_rounds')
    outputFileNames = settings.get('general', 'experiment_name')
    # how many sampled sequence to output each round, stored in output_samples_Ri.txt
    samplingSize = settings.getint('general', 'sampling_size')
    post_process = settings.getboolean('general', 'post_process')
    img_format = settings.get('general', 'img_format')

    # how many sequence to select each round
    initialSamples = settings.getint('selectionparams', 'initial_samples')
    selectionThreshold = settings.getint('selectionparams', 'scale')
    distanceMeasure = settings.get('selectionparams', 'distance')
    stringency = settings.getint('selectionparams', 'stringency')

    pcrCycleNum = settings.getint('amplificationparams', 'number_of_pcr')
    pcrYield = settings.getfloat('amplificationparams', 'pcr_efficiency')
    pcrErrorRate = settings.getfloat('amplificationparams', 'pcr_error_rate')
    pcrBias = settings.getfloat('amplificationparams', 'pcr_bias')

    def call_post_process(target):
        import postprocess
        print("Data post-processing has started...")
        postprocess.dataAnalysis(seqLength, roundNum, outputFileNames, post_process, distanceMeasure, imgformat=img_format)
        # postprocess.dataAnalysis(seqLength, roundNum, "{}_samples".format(outputFileNames),
        #                          post_process, distanceMeasure, imgformat=img_format)
        postprocess.plot_histo(roundNum, outputFileNames, target, "png", "hamming")
        postprocess.plot_histo(roundNum, "{}_samples".format(outputFileNames), target, "png", "hamming")
        print("Data post-processing is complete.")
        return

    if postprocess_only:
        call_post_process(aptamerSeq)
        sys.exit()

    D = Distance(pcrBias)
    S = Selection(distanceMeasure, selectionThreshold, initialSamples, samplingSize, stringency, D)

    if rng_seed == 0:
        rng_seed = random.randint(0, 2**32)
    print("Random seed: {}".format(rng_seed))
    random.seed(rng_seed)
    np.random.seed(rng_seed)

    # SELEX simulation based on random aptamer assignment, hamming-based definite selection, and
    # non-ideal stochastic amplfication with no bias.
    if(aptamerType == 'DNA'):
        alphabetSet = 'ACGT'
    elif(aptamerType == 'RNA'):
        alphabetSet = 'ACGU'
    else:
        print("Error: Simulation of %.s aptamers not supported" % aptamerType)
        sys.exit()

    # Instantiating classes
    Apt = Aptamers(alphabetSet, seqLength)
    Amplify = Amplification()

    # initialize Mutation object from class
    mut = Mutation(D, seqLength=Apt.seqLength, errorRate=pcrErrorRate,
                   pcrCycleNum=pcrCycleNum, pcrYld=pcrYield)

    if aptamerNum > 0:
        aptamerSeqs, initialSeqNum = Apt.optimumAptamerGenerator(aptamerNum)
    else:
        aptamerSeqs = aptamerSeq
        initialSeqNum = len(alphabetSet)**len(aptamerSeq)
    if len(aptamerSeqs) > 1:
        print("optimum sequences have been chosen: {}".format(aptamerSeqs))
    else:
        print("optimum sequence has been chosen: {}".format(aptamerSeqs))
    assert len(aptamerSeq) == seqLength
    print("seq length = "+str(seqLength))

    for r in range(roundNum+1):
        if(r == 0):
            header = "Creating initial library"
            print(header)
            print("-"*len(header))
            print("total number of sequences in initial library = "+str(initialSeqNum), flush=True)
            amplfdSeqs = S.stochasticSelection_initial(Apt, aptamerSeqs, initialSeqNum, outputFileNames, r)
        else:
            header = "SELEX Round "+str(r)+" has started"
            print(header)
            print("-"*len(header))
            totalSeqNum, uniqSeqNum = utils.seqNumberCounter(amplfdSeqs)
            print("total number of sequences in initial pool = "+str(totalSeqNum))
            print("total number of unique sequences in initial pool = "+str(int(uniqSeqNum)), flush=True)
            amplfdSeqs = S.stochasticSelection(Apt, amplfdSeqs, outputFileNames, r)
            print("Selection carried out for R"+str(r))
        amplfdSeqs = Amplify.randomPCR_with_ErrorsAndBias(amplfdSeqs, mut, aptamerSeqs, Apt, distanceMeasure)
        print("Amplification carried out for R"+str(r))
        outFile = outputFileNames + "_R{:03d}".format(r)
        nxtRnd = open(outFile, 'w')
        print("writing R"+str(r)+" seqs to file")
        for seqIdx in amplfdSeqs:
            seq = Apt.pseudoAptamerGenerator(seqIdx)
            # write seq, distance, and count for now
            nxtRnd.write(str(seq)+'\t'+str(int(amplfdSeqs[seqIdx][1]))+'\t'+str(int(amplfdSeqs[seqIdx][0]))+'\n')
        nxtRnd.close()
    print("SELEX completed")

    if post_process:
        call_post_process(aptamerSeqs)
        print("The simulation has ended.")
    else:
        print("The simulation has ended without post-processing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parse arguments.')
    parser.add_argument('-p', '--postprocess', action='store_true')
    parser.add_argument('-s', '--settings', type=str, default="settings.init")

    args = parser.parse_args()

    if not os.path.exists(args.settings):
        print("Settings file '{}' does not exists, aborting.".format(args.settings))
        sys.exit()

    main_sim(args.settings, args.postprocess)
