import qmcpy as qp 

# lattice
# https://qmcpy.readthedocs.io/en/latest/algorithms.html#module-qmcpy.discrete_distribution.lattice.lattice 
lattice = qp.Lattice(
    dimension = 3,
    generating_vector = "LDData/main/lattice/mps.exew_base2_m20_a3_HKKN.txt",
    randomize = False # set to True to apply random shift 
)
x = lattice(0,8) # points from index 0 (inclusive) to 8 (exclusive)
print(x) 

# digital net in base 2 
# https://qmcpy.readthedocs.io/en/latest/algorithms.html#module-qmcpy.discrete_distribution.digital_net_b2.digital_net_b2
dnb2 = qp.DigitalNetB2(
    dimension = 3,
    generating_matrices = "LDData/main/dnet/mps.sobol_Cs.txt",
    randomize = False # set to True to apply left linear matrix scrambling with digital shift 
    # other randomization options are also supported
)
x = dnb2(0,8) # points from index 0 (inclusive) to 8 (exclusive)
print(x)