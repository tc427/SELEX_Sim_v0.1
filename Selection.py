import numpy as np
import utils

# append path for ViennaRNA module
import RNA


# NEED TO CHANGE SAMPLING FOR SELECTION TO BE WEIGHTED BY COUNT OF EACH UNIQUE SEQ

# number of random samples to draw at a time
Nrsamples = 10**4


class Selection:
    def __init__(self, distname, selectionThreshold, initialSize, samplingSize, stringency, dist):
        self.distances = ("hamming", "basepair", "loop", "random")
        self.distname = distname
        self.dist = dist
        self.selectionThreshold = selectionThreshold
        self.initialSize = initialSize
        self.samplingSize = samplingSize
        self.stringency = stringency
        if self.distname not in self.distances:
            print("Invalid argument for distance measure")
            raise
        self.distance = None
        if self.distname == "hamming":
            self.distance = self.dist.hamming_func
        elif self.distname == "basepair":
            self.distance = self.dist.bp_func
        elif self.distname == "loop":
            self.distance = self.dist.loop_func
        elif self.distname == "random":
            self.distance = self.dist.nodist_func

    def createInitialLibrary(self, apt, totalSeqNum, aptref):
        seqPool = dict()
        for randIdx in utils.randint(0, int(totalSeqNum-1), size=self.initialSize):
            if randIdx in seqPool:
                seqPool[randIdx][0] += 1
            else:
                randSeq = apt.pseudoAptamerGenerator(randIdx)
                randSeqBias = self.dist.bias_func(randSeq, apt.seqLength)
                randSeqDist = self.distance(aptref, randSeq)
                seqPool[randIdx] = np.array([1, randSeqDist, randSeqBias])
        return seqPool

    def createInitialLibrary_loop(self, apt, totalSeqNum, seqref, structref, loopref):
        seqPool = dict()
        for randIdx in utils.randint(0, int(totalSeqNum-1), size=self.initialSize):
            if randIdx in seqPool:
                seqPool[randIdx][0] += 1
            else:
                randSeq = apt.pseudoAptamerGenerator(randIdx)
                randSeqBias = self.dist.bias_func(randSeq, apt.seqLength)
                randSeqDist = self.dist.loop_func(seqref, structref, loopref, apt.seqLength, randSeq)
                seqPool[randIdx] = np.array([1, randSeqDist, randSeqBias])
        return seqPool

    def stochasticSelection_initial(self, apt, aptPool,
                                    totalSeqNum,
                                    outputFileNames, rnd):
        slctdSeqs = None
        ref = aptPool
        if self.distname == "basepair":
            ref = RNA.fold(aptPool)[0]
            print("Optimum aptamer structure: {}".format(ref))
        print("Creating initial library...", flush=True)
        # stochastic selection until threshold is met
        if self.distname == "loop":
            aptStruct = RNA.fold(aptPool)[0]
            print("Optimum aptamer structure: {}".format(aptStruct))
            aptLoop = utils.apt_loopFinder(aptPool, aptStruct, apt.seqLength)
            slctdSeqs = self.createInitialLibrary_loop(apt, totalSeqNum, aptPool, aptStruct, aptLoop)
        else:
            slctdSeqs = self.createInitialLibrary(apt, totalSeqNum, ref)
        print("Initial library created")
        selectionDist = utils.rv_int(slctdSeqs, "selectionDist")
        print("Sampling has started...")
        self.samplingProcess(apt, slctdSeqs, selectionDist, self.samplingSize,
                             outputFileNames, rnd)
        print("Sampling has completed")
        return slctdSeqs

    def stochasticSelection(self, apt, seqPool,
                            outputFileNames, rnd):
        # initialize selected sequence pool
        print("seq selection threshold = "+str(self.selectionThreshold))
        # compute sampling distribution for selection
        # using count of each unique seq
        selectionDist = utils.rv_int(seqPool, "selectionDist")
        print("Sampling has started...")
        self.samplingProcess(apt, seqPool, selectionDist, self.samplingSize,
                             outputFileNames, rnd)
        print("Sampling has completed")
        # reset all seq counts prior to selection
        for k in seqPool:
            seqPool[k][0] = 0
        # draw a bunch of random seqs
        self.selectionProcess(seqPool, selectionDist, apt.seqLength)
        # remove all seqs that haven't been selected
        for ki in [k for k, v in seqPool.items() if v[0] == 0]:
            del seqPool[ki]
        print("sequence selection has been carried out")
        return seqPool

    def samplingProcess(self, apt,
                        seqPool, selectionDist, samplingSize,
                        outputFileNames, rnd):
        samps = dict()
        # draw random samples from distribution
        for seqIdx in selectionDist.rvs(size=samplingSize):
            if seqIdx in samps:
                samps[seqIdx] += 1
            else:
                samps[seqIdx] = 1
        sampleFileName = outputFileNames+"_samples_R{:03d}".format(rnd)
        # write to samples file
        with open(sampleFileName, 'w') as s:
            for seqIdx, N in samps.items():
                seq = apt.pseudoAptamerGenerator(seqIdx)
                s.write(str(seq)+'\t'+str(int(seqPool[seqIdx][1]))+'\t'+str(N)+'\n')
        return

    # This function takes an empty selected pool, aptamer sequence structure and loop,
    # number of target binding sites, the alphabet set of the molecule, length,
    # total sequence number and stringency factor and returns full selected pool
    # Input: np.array(), int(), stats.obj(), int()
    # Output: np.array()
    def selectionProcess(self, seqPool, selectionDist, seqLength):
        selectedSeqs = 0
        # until all sites are occupied
        print("Drawing sample batch")
        while(selectedSeqs < self.selectionThreshold):
            # draw random sequences
            # warning: looping here causes large memory consumption
            for randIdx in selectionDist.rvs(size=Nrsamples):
                # carry out stochastic selection
                # draw random affinities
                if(int(seqPool[randIdx][1]) < utils.randint(0, seqLength-self.stringency)):
                    seqPool[randIdx][0] += 1
                    selectedSeqs += 1
                    if selectedSeqs % Nrsamples == 0:
                        print("{}% completed".format(100.0*selectedSeqs/self.selectionThreshold))
        return
