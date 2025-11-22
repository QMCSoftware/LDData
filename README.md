# LDData: Low-Discrepancy Generating Vectors and Matrices

A curated collection of **low-discrepancy point set parameters** including **lattice rules**, **digital nets**, **polynomial lattice rules**, **Sobol' nets**, and **RQMC randomizations**.  This dataset enables reproducible research and high-performance Quasi–Monte Carlo (QMC) and Randomized QMC (RQMC) simulation.

The [LDData repository](https://github.com/QMCSoftware/LDData) provides **standard text-based formats** for specifying structures used in QMC point generation across arbitrarily high dimensions.

---

## Dataset Summary

LDData is a dataset of structured parameter files defining:

- Rank-1 **lattice rules**
- Base-$b$ **digital nets**
- **Polynomial lattice rules**
- **Sobol' and Sobol–Joe-Kuo sequences**
- Various **randomizations** (shift modulo 1, digital shifts, nested uniform
  scrambles, left matrix scrambles)

Each file type follows a simple textual standard to ensure:
- Human readability  
- Language-agnostic parsing  
- Long-term reproducibility  
- Extensibility to thousands of dimensions  

The dataset is motivated by the need for **standardized, compact, transparent formats** in [our QMC research and software](https://github.com/QMCSoftware).

---

## Motivation

Many QMC constructions appear across scattered software packages, papers, or custom formats. LDData brings these formats together into a **consistent, unified, machine-readable** repository for:

- Researchers developing new QMC methods  
- Practitioners needing high-dimensional low-discrepancy point sets  
- Developers of simulation libraries such as SSJ, QMCPy, and LatNet Builder  

This dataset is linked to the research works described in the Citation section below. **For detailed technical specifications and implementation details**, see
[LD_DATA.md](LD_DATA.md)

---

## Supported Tasks and Applications

### ✔️ Quasi-Monte Carlo (QMC)
Generate deterministic point sets with excellent equidistribution.

### ✔️ Randomized QMC (RQMC)
Use the included randomizations for variance estimation:
- Digital shifts  
- Nested uniform scrambles  
- Left-matrix scrambles  

### ✔️ High-dimensional Integration and Simulation

Used in:
- Bayesian computation  
- Option pricing
- High-dimensional PDE solvers  
- Uncertainty quantification  
- Graphics and rendering research  
- Machine learning sampling methods  

### ✔️ Benchmarking
Standard formats help evaluate new constructions against established ones.

---

## Features

- Simple `.txt` formats with **one line per dimension**
- Optional human-readable comments starting with `#`
- No binary encoding or word-size assumptions
- Supports extremely high dimensions (10,000+)
- Extensible constructions (e.g., Sobol or embedded nets)
- All formats interoperable with QMC software (SSJ, QMCPy, LatNet Builder)

---

## How to Use the Dataset

### Load files directly from Hugging Face

```python
from datasets import load_dataset

ds = load_dataset("QMCSoftware/LDData")
```

All data files are preserved in their directory structure and can be accessed
using:

```python
ds["train"]  # or ds['default']
```

### Typical workflow

1. Read a parameter file (e.g. `lattice_8d.txt`)
2. Parse header (`# lattice`, dimensions, n, etc.)
3. Parse one line per dimension for the generating vector or matrices
4. Construct QMC point generator in your preferred library

---

## Dataset Structure

The dataset includes multiple categories of files:

### 🔹 `lattice`  
Rank-1 lattice generating vectors:  
- Header: `# lattice`  
- Parameters:  
  - Number of dimensions `s`  
  - Number of points `n`  
  - `s` lines of generating vector coefficients  

---

### 🔹 `dnet`  
General digital nets in base `b`:  
- Header: `# dnet`  
- Parameters:  
  - Base `b`  
  - Dimensions `s`  
  - Columns `k`  
  - Rows `r`  
- Then `s` lines representing generating matrices

Efficient for high-dimensional digital nets.

---

### 🔹 `plattice`  
Polynomial lattice rules:  
- Compact format using integer-encoded polynomials  
- Base `b`, dimension `s`, polynomial degree `k`, and generating polynomials

---

### 🔹 `sobol` and `soboljk`  
Parameters for Sobol' sequences:  
- `soboljk`: Joe & Kuo format with primitive polynomials and direction numbers  
- `sobol`: Simplified direction-number only format  

Used widely in QMC applications.

---

### 🔹 Randomization formats

Includes:

- `shiftmod1`: Shift modulo 1  
- `dshift`: Digital shift in base `b`  
- `nuscramble`: Nested uniform scramble  
- `lmscramble`: Left matrix scramble  

All formats are text-based and reproducible.

---

## Example: Parsing a Lattice Rule File

Example file:

```
# lattice
8
65536
1 
19463
17213
5895
14865
31925
30921
26671
```

Python pseudo-code:

```python
with open("lattice_8d.txt") as f:
    lines = [l for l in f.readlines() if not l.startswith("#")]

s = int(lines[0])
n = int(lines[1])
a = [int(x) for x in lines[2:2+s]]
```

---

## File Naming Recommendations

To support discoverability and consistent tooling:

- All files begin with their keyword (`lattice_`, `dnet_`, `sobol_`, etc.)
- Headers contain:
  - Construction method  
  - Figure of merit (FOM)  
  - Weights  
  - Embedded range (if applicable)  
- Comments allowed in headers only  

---

## References

This dataset incorporates formats and ideas from foundational work in QMC:

- Bratley & Fox (1988)  
- Joe & Kuo (2008)  
- L’Ecuyer (2016)  
- Goda & Dick (2015)  
- Nuyens (2020)  
- And others listed in the detailed specification [LD_DATA.md](LD_DATA.md).

---

## Citation

If you use LDData in academic work, please cite:

```
@article{sorokin2025,
  title               = {{QMCPy}: a {P}ython software for randomized low-discrepancy sequences, quasi-{M}onte {C}arlo, and fast kernel methods},
  author              = {Aleksei G. Sorokin},
  year                = {2025},
  journal             = {ArXiv preprint},
  volume              = {abs/2502.14256},
  url                 = {https://arxiv.org/abs/2502.14256},
}


@inproceedings{choi2022,
  title               = {Quasi-{M}onte {C}arlo software},
  author              = {Choi, Sou-Cheng T. and Hickernell, Fred J. and Rathinavel, Jagadeeswaran and McCourt, Michael J. and Sorokin, Aleksei G.},
  year                = {2022},
  booktitle           = {{M}onte {C}arlo and Quasi-{M}onte {C}arlo Methods 2020},
  publisher           = {Springer International Publishing},
  address             = {Cham},
  pages               = {23--47},
  isbn                = {978-3-030-98319-2},
  editor              = {Keller, Alexander},
}
```

---

## License

Apache 2 License.  
See [`LICENSE`](LICENSE.txt) file for details.

---

## Acknowledgements

This dataset is developed and maintained by:

- **QMCSoftware team**  
- Contributors to QMCPy, SSJ, and LatNet Builder  
- Community contributions from QMC & RQMC researchers

Special thanks to researchers providing widely used generating vectors and direction numbers used throughout the scientific computing community.
