#!/usr/bin/env python
# Based on https://gist.github.com/oberstet/f492fe987d5d746cba5b0880e9f33d5b

import os
import math
from pprint import pprint, pformat

import numpy as np
from matplotlib import pyplot

from CSXCAD import ContinuousStructure, AppCSXCAD_BIN
from CSXCAD.CSProperties import CSPropMetal

from openEMS import openEMS
from openEMS.physical_constants import C0

# enable NF2FF recording, computation and plotting
enable_nf2ff = True

# not only render, but also fire up matplotlib to show the plots
enable_show_plots = True

# fire up AppCSXCAD for viewing the model before running it
enable_appcsxcad = True

# all units are in mm
unit = 1e-3

# =============================
# **! Yagi antenna settings !**
# =============================
director_length = 864
director_dist = 263
director_side_boom_additional_len = 50

driven_length = 902

reflector_length = 951
reflector_dist = 311
reflector_side_boom_additional_len = 200

# https://www.meiacolher.com/2018/10/medidas-dos-canos-de-pvc-saiba-bitola.html
boom_ext_radius = 25
boom_shell_width = 1.7

# https://smarc.org.au/wp-content/uploads/2021/11/Hairpin-Matching-VK2DEQ.pdf
hairpin_enable = True
# https://i0.wp.com/cref.if.ufrgs.br/wp-content/uploads/2018/06/fig4_bitolafio.png
hairpin_wire_diameter = 2.26
hairpin_length = 58
hairpin_D = 10
# =============================

# excitation frequency and bandwidth
f0 = 145.825e6

# excitation bandwidth
fc = 0.3 * f0

# length factor to apply to reach fixed point of resonance frequency
# being identical to excitation frequency
# "Found resonance frequency at 500 MHz with -44 dB at 71 Ohm"

# Correction factor to shorten the wavelength used from theoretical value to account
# for XXX
#
# Found resonance frequency at 446.1 MHz with -80.4 dB at 71.0 Ohm
# Dipole (lambda/2) length is 290.7 mm
#
# opt_factor = 0.8625

# use with driven_wire_radius = 0.001
# opt_factor = 0.8651

# use with driven_wire_radius = 2.0
# Found resonance frequency at 446.1 MHz with -80.5 dB at 70.8 Ohm
# Dipole (lambda/2) length is 285.8 mm
opt_factor = 0.8506

# wave length to compute antenna length from
# lambda0 = round(opt_factor * C0 / 500e6 / unit)
lambda0 = opt_factor * C0 / f0 / unit

# gap in between the two driven arms (the lumped port will fill that)
driven_gap = 1.0

# driven_wire_radius = 0.001
# driven_wire_radius = 1.0
driven_wire_radius = 2.0

# Radiation resistance (ohms)
# https://en.wikipedia.org/wiki/Radiation_resistance#Radiation_resistance_of_common_antennas
# feed_resistance = 73.1
# feed_resistance = 71.0
feed_resistance = 50

# Overlap of lumped port (driven feed) with the actual driven arms excited
# Note: MUST be non-zero, and actually >>0, not sure ..
feed_overlap = 0.1
# feed_overlap = 0.5
# feed_overlap = 1.0

max_res = math.floor(C0 / (f0 + fc) / unit / 20)
sim_box = np.array([1, 1, 1]) * 2.0 * lambda0
# nf_ff_transition_distance = math.ceil(lambda0 / (2 * math.pi))
nf_ff_transition_distance = 2 * lambda0

output_dir = os.path.abspath(os.path.join("results", "yagi_trena"))
if not os.path.isdir(output_dir):
    os.mkdir(output_dir)

class Trena:
    thickness = 0.2
    points = [[-10.875,-11.000,-10.054,-7.565,-5.901,-4.042,-2.057,-1.032,0.000,1.032,2.057,4.042,5.901,7.565,10.054,11.000,10.875,9.937,7.462,5.815,3.978,2.014,1.012,0.000,-1.012,-2.014,-3.976,-5.815,-7.462,-9.937],[4.900,4.744,3.988,2.325,1.435,0.658,0.109,-0.045,-0.100,-0.045,0.109,0.658,1.435,2.325,3.988,4.744,4.900,4.150,2.497,1.616,0.847,0.304,0.154,0.099,0.154,0.304,0.847,1.616,2.497,4.150]]
    @classmethod
    def translate_to(cls, xc, yc):
        return [[x+xc for x in cls.points[0]], [y+yc for y in cls.points[1]]]

# Radius of lumped port (driven feed port)
feed_radius = Trena.thickness / (2*math.sqrt(2))

fdtd = openEMS(NrTS=3e5, EndCriteria=1e-4)
fdtd.SetGaussExcite(f0, fc)
fdtd.SetBoundaryCond(["MUR", "MUR", "MUR", "MUR", "MUR", "MUR"])

csx = ContinuousStructure()
fdtd.SetCSX(csx)
mesh = csx.GetGrid()
mesh.SetDeltaUnit(unit)

# create mesh and geometry for yagi; the yagi elements are oriented along the Z-axis (!)

# **!: dense mesh in port region
mesh.AddLine("z", np.linspace(-driven_gap / 2 - feed_overlap, driven_gap / 2 + feed_overlap, 5))

# **!: dense mesh around ends of arms
min_length = min(director_length, driven_length, reflector_length)
max_length = max(director_length, driven_length, reflector_length)
mesh.AddLine("z", np.linspace(-max_length / 2 - 5 * driven_wire_radius, -min_length / 2 + 5 * driven_wire_radius, 11))
mesh.AddLine("z", np.linspace(min_length / 2 - 5 * driven_wire_radius, max_length / 2 + 5 * driven_wire_radius, 11))
if hairpin_enable:
    mesh.AddLine("z", [-hairpin_D/2, hairpin_D/2])
# mesh.AddLine("z", [-driven_gap / 2 - driven_length / 2, driven_gap / 2 + driven_length / 2])
mesh.AddLine("z", [-sim_box[0] / 2, 0, sim_box[0] / 2])
mesh.SmoothMeshLines("z", max_res, ratio=1.4)

mesh.AddLine("y", [-boom_shell_width/2 - Trena.thickness/2])
mesh.AddLine("y", [-sim_box[1] / 2, 0, sim_box[1] / 2])
mesh.SmoothMeshLines("y", max_res, ratio=1.4)

if hairpin_enable:
    mesh.AddLine("x", [hairpin_length])
mesh.AddLine("x", [-reflector_dist, director_dist])
mesh.AddLine("x", [-sim_box[2] / 2, 0, sim_box[2] / 2])
mesh.SmoothMeshLines("x", max_res, ratio=1.4)

driven_arm1: CSPropMetal = csx.AddMetal("driven_arm1")
# port gap is part of the total driven length (!):
#driven_arm1.AddWire([[0, 0], [0, 0], [-driven_gap / 2, -driven_length / 2]], radius=driven_wire_radius)
driven_arm1.AddLinPoly(points=Trena.translate_to(0, 0), norm_dir='z', elevation=-driven_length/2, length=driven_length/2-driven_gap/2)
driven_arm1.SetColor("#ff0000", 50)

driven_arm2: CSPropMetal = csx.AddMetal("driven_arm2")
# port gap is part of the total driven length (!):
#driven_arm2.AddWire([[0, 0], [0, 0], [driven_gap / 2, driven_length / 2]], radius=driven_wire_radius)
driven_arm2.AddLinPoly(points=Trena.translate_to(0, 0), norm_dir='z', elevation=driven_gap/2, length=driven_length/2-driven_gap/2)
driven_arm2.SetColor("#ff0000", 50)

if hairpin_enable:
    hairpin: CSPropMetal = csx.AddMetal("hairpin")
    hairpin.AddWire([[0, hairpin_length], [0, 0], [-hairpin_D/2, -hairpin_D/2]], radius=hairpin_wire_diameter/2)
    hairpin.AddWire([[0, hairpin_length], [0, 0], [ hairpin_D/2,  hairpin_D/2]], radius=hairpin_wire_diameter/2)
    hairpin.AddWire([[hairpin_length, hairpin_length], [0, 0], [-hairpin_D/2, hairpin_D/2]], radius=hairpin_wire_diameter/2)
    hairpin.SetColor("#0000ff", 50)

director_arm: CSPropMetal = csx.AddMetal("director_arm")
director_arm.AddLinPoly(points=Trena.translate_to(director_dist, 0), norm_dir='z', elevation=-director_length/2, length=director_length)
director_arm.SetColor("#ff0000", 50)

reflector_arm: CSPropMetal = csx.AddMetal("reflector_arm")
reflector_arm.AddLinPoly(points=Trena.translate_to(-reflector_dist, 0), norm_dir='z', elevation=-reflector_length/2, length=reflector_length)
reflector_arm.SetColor("#ff0000", 50)

boom = csx.AddMaterial('PVC')
# sources:
# - https://passive-components.eu/what-is-dielectric-constant-of-plastic-materials/
# - https://matmake.com/properties/relative-permittivity-of-common-materials.html
# - https://matmake.com/properties/magnetic-permeability-of-common-materials.html
boom.SetMaterialProperty(epsilon=4, mue=1.000058)
boom.AddCylindricalShell(start=[-reflector_dist-reflector_side_boom_additional_len,-boom_ext_radius-boom_shell_width/2-Trena.thickness/2,0], stop=[director_dist+director_side_boom_additional_len,-boom_ext_radius-boom_shell_width/2-Trena.thickness/2,0], radius=boom_ext_radius-boom_shell_width/2, shell_width=boom_shell_width)
boom.SetColor("#00ff00", 50)

feed = fdtd.AddLumpedPort(
    1,
    feed_resistance,
    [-feed_radius, -feed_radius, -driven_gap / 2 - feed_overlap],
    [feed_radius, feed_radius, driven_gap / 2 + feed_overlap],
    "z",
    1.0,
    priority=5,
)

#########################################################################################
# setup far-field recording
#
if enable_nf2ff:
    # wavelength of minimum/maximum frequency used (in excitation) in simulation
    min_freq_lambda = round(C0 / (f0 - fc) / unit)
    max_freq_lambda = round(C0 / (f0 + fc) / unit)

    # distance of transition between near-field to far-field
    nf_ff_transition_distance = math.ceil(min_freq_lambda / (2 * math.pi))

    # simulation mesh resolution for far-field
    mesh_res_farfield = round(max_freq_lambda / 30)

    # add the NF2FF recording box
    start = [-nf_ff_transition_distance / 2] * 3
    stop = [nf_ff_transition_distance / 2] * 3
    nf2ff = fdtd.CreateNF2FFBox("nf2ff-box", start=start, stop=stop, opt_resolution=[mesh_res_farfield] * 3)

    # smooth out mesh for far-field
    # mesh.SmoothMeshLines("all", mesh_res_farfield, 1.4)

#########################################################################################
# fire up AppCSXCAD for viewing the model before running it
#
output_fn = os.path.join("models", "yagi_trena.xml")
csx.Write2XML(output_fn)
if enable_appcsxcad:
    os.system('{} "{}"'.format(AppCSXCAD_BIN, output_fn))

#########################################################################################
#
fdtd.Run(output_dir, verbose=3, cleanup=True)

# Found resonance frequency at 446.2 MHz with -42.5 dB at 71.1 Ohm
# Dipole (lambda/2) length is 289.8 mm
freq = np.linspace(f0 - fc, f0 + fc, 2001)
feed.CalcPort(output_dir, freq)

Zin = feed.uf_tot / feed.if_tot
s11 = feed.uf_ref / feed.uf_inc
s11_dB = 20.0 * np.log10(np.abs(s11))

# Found resonance frequency at 446.1 MHz with -42.4 dB at 71.0 Ohm
# Dipole (lambda/2) length is 289.8 mm
print(s11_dB)
print(freq)
print(type(s11_dB), len(s11_dB))
print(type(freq), len(freq))

cutoff_db_resonance = -4
cutoff_dbs = [cutoff_db_resonance, -1, -2, -3]
cutoff_dbs_results = {}

#idx = np.where((s11_dB < cutoff_db_resonance) & (s11_dB == np.min(s11_dB)))[0]
idx = np.where((s11_dB == np.min(s11_dB)))[0]
if not len(idx) == 1:
    print("No resonance frequency found for far-field calculation!")
else:
    print("\n")
    print("=" * 80)
    print("")
    print(
        "Found resonance frequency at {} MHz with {} dB at {} Ohm".format(
            round(freq[idx][0] / 1e6, 1),
            round(s11_dB[idx][0], 1),
            round(np.real(Zin[idx])[0], 1),
        )
    )
    print("Driven length is {} mm".format(round(driven_length, 1)))
    print("")
    print("=" * 80)
    print("")

    cutoff_dbs_results["interest"] = {}
    cutoff_interest_bw = round((446.2e6 - 446.0e6) / 1e6, 1)
    for kf, f in [("lower", 446.0e6), ("center", 446.1e6), ("upper", 446.2e6)]:
        # Calculate absolute differences
        abs_diff = np.abs(freq - f)
        # Find the index of the closest value
        closest_index = np.argmin(abs_diff)
        print(
            "S11 at frequency {} MHz is {} dB at {} Ohm [index {}]".format(
                round(f / 1e6, 1),
                round(s11_dB[closest_index], 1),
                round(np.real(Zin[closest_index]), 1),
                closest_index,
            )
        )
        cutoff_dbs_results["interest"][kf] = {
            "idx": closest_index,
            "freq": round(freq[closest_index] / 1e6, 1),
            "s11": round(s11_dB[closest_index], 1),
            "r": round(np.real(Zin[closest_index]), 1),
            "bandwidth": cutoff_interest_bw,
        }
    print("")

    for cutoff_db in cutoff_dbs:
        idx_cutoff_lower = idx[0]
        while idx_cutoff_lower >= 0 and s11_dB[idx_cutoff_lower] < cutoff_db:
            idx_cutoff_lower -= 1
        # print("cutoff_lower index: {}".format(idx_cutoff_lower))

        idx_cutoff_upper = idx[0]
        while idx_cutoff_upper <= len(s11_dB) and s11_dB[idx_cutoff_upper] < cutoff_db:
            idx_cutoff_upper += 1
        # print("cutoff_upper index: {}".format(idx_cutoff_upper))

        print("")
        print(
            "S11 at frequency {} MHz is {} dB at {} Ohm".format(
                round(freq[idx_cutoff_lower] / 1e6, 1),
                round(s11_dB[idx_cutoff_lower], 1),
                round(np.real(Zin[idx_cutoff_lower]), 1),
            )
        )
        print(
            "S11 at frequency {} MHz is {} dB at {} Ohm".format(
                round(freq[idx_cutoff_upper] / 1e6, 1),
                round(s11_dB[idx_cutoff_upper], 1),
                round(np.real(Zin[idx_cutoff_upper]), 1),
            )
        )

        cutoff_dbs_results[cutoff_db] = {}
        cutoff_dbs_results[cutoff_db]["lower"] = {
            "idx": idx_cutoff_lower,
            "freq": round(freq[idx_cutoff_lower] / 1e6, 1),
            "s11": round(s11_dB[idx_cutoff_lower], 1),
            "r": round(np.real(Zin[idx_cutoff_lower]), 1),
        }
        cutoff_dbs_results[cutoff_db]["upper"] = {
            "idx": idx_cutoff_upper,
            "freq": round(freq[idx_cutoff_upper] / 1e6, 1),
            "s11": round(s11_dB[idx_cutoff_upper], 1),
            "r": round(np.real(Zin[idx_cutoff_upper]), 1),
        }
        cutoff_dbs_results[cutoff_db]["bandwidth"] = round((freq[idx_cutoff_upper] - freq[idx_cutoff_lower]) / 1e6, 1)

    print("=" * 80)
    print("\n")

#########################################################################################
# plot the feed point impedance
#
pyplot.figure()
pyplot.plot(freq / 1e6, np.real(Zin), "k-", linewidth=2, label=r"$\Re(Z_{in})$")
pyplot.grid()
pyplot.plot(freq / 1e6, np.imag(Zin), "r--", linewidth=2, label=r"$\Im(Z_{in})$")
pyplot.title("feed point impedance")
pyplot.xlabel("frequency (MHz)")
pyplot.ylabel("impedance (Omega)")
pyplot.legend()
pyplot.savefig('fig_impedance.svg')

#########################################################################################
# plot reflection coefficient S11
#
pyplot.figure()
pyplot.plot(freq / 1e6, s11_dB, "k-", linewidth=2, label="$S_{11}$")
pyplot.grid()
pyplot.title(
    "Yagi-Uda for {} MHz\nAntenna Efficiency: S11 Reflection Coefficient vs Frequency\n".format(
        round(f0 / 1e6, 1)
    )
)
pyplot.ylabel("Reflection coefficient $S_{11}$ (dB)")
pyplot.xlabel("Frequency (MHz)")
# pyplot.legend()

# Calculate alpha values based on s11_dB
min_alpha = 0.05
max_alpha = 0.8

alpha_values = (s11_dB - cutoff_db_resonance) / (s11_dB.min() - cutoff_db_resonance)
alpha_values = np.clip(alpha_values, 0, 1)  # Clip values between 0 and 1
alpha_values = min_alpha - alpha_values * (min_alpha - max_alpha)


# Add vertical lines colored based on s11_dB values
idx_cutoff_lower = cutoff_dbs_results[cutoff_db_resonance]["lower"]["idx"]
idx_cutoff_upper = cutoff_dbs_results[cutoff_db_resonance]["upper"]["idx"]

res_cutoff_interest_lower = cutoff_dbs_results["interest"]["lower"]
res_cutoff_interest_upper = cutoff_dbs_results["interest"]["upper"]

pprint(res_cutoff_interest_lower)
pprint(res_cutoff_interest_upper)

# index of _maximum_ of S11 at both ends of frequency band of interest
idx_cutoff_interest = (
    res_cutoff_interest_lower["idx"]
    if res_cutoff_interest_lower["s11"] > res_cutoff_interest_upper["s11"]
    else res_cutoff_interest_upper["idx"]
)
print(">>" * 100, idx_cutoff_lower, idx_cutoff_upper, idx, idx_cutoff_interest)

for i in range(len(freq)):
    if idx_cutoff_lower <= i <= idx_cutoff_upper:
        if i == idx_cutoff_lower or i == idx_cutoff_upper:
            pyplot.axvline(x=freq[i] / 1e6, color="green", alpha=1.0, zorder=2)
        elif i == idx:
            pyplot.axvline(x=freq[i] / 1e6, color="blue", alpha=1.0, zorder=2)
            pyplot.axhline(y=round(s11_dB[idx][0], 1), color="blue", alpha=1.0, zorder=2)
        elif i == idx_cutoff_interest:
            pyplot.axhline(y=round(s11_dB[i], 1), color="blue", alpha=1.0, zorder=2, linestyle="--")
            pyplot.text(
                round(freq[i] / 1e6, 1),
                round(s11_dB[i], 1) + 1.0,
                "{} MHz bandwidth @ {} dB".format(res_cutoff_interest_lower["bandwidth"], round(s11_dB[i], 1)),
                ha="center",
                zorder=4,
                fontweight="bold",
            )
        elif i % 2:
            pyplot.axvline(x=freq[i] / 1e6, color="green", alpha=alpha_values[i], zorder=0, linestyle="dotted")

x = round(freq[idx][0] / 1e6, 1)
for cutoff_db in cutoff_dbs:
    pyplot.axhline(y=cutoff_db, color="green", alpha=1.0, linestyle="dotted")
    pyplot.text(
        x,
        cutoff_db + 1.0,
        "{} MHz bandwidth @ {} dB".format(cutoff_dbs_results[cutoff_db]["bandwidth"], cutoff_db),
        ha="center",
        zorder=4,
        fontweight="bold",
    )

    idx_cutoff_lower = cutoff_dbs_results[cutoff_db]["lower"]["idx"]
    idx_cutoff_upper = cutoff_dbs_results[cutoff_db]["upper"]["idx"]

    # Add markers with text to specific coordinates
    markers = [
        {
            "pos": (freq[idx_cutoff_lower] / 1e6, s11_dB[idx_cutoff_lower]),
            "offset": [-4.0, -4.0],
            "text": " {} MHz: {} dB\n@ {} Ohm".format(
                round(freq[idx_cutoff_lower] / 1e6, 1),
                round(s11_dB[idx_cutoff_lower], 1),
                round(np.real(Zin[idx_cutoff_lower]), 1),
            ),
            "color": "red",
            "ha": "right",
        },
        {
            "pos": (freq[idx_cutoff_upper] / 1e6, s11_dB[idx_cutoff_upper]),
            "offset": [4.0, -4.0],
            "text": " {} MHz: {} dB\n@ {} Ohm".format(
                round(freq[idx_cutoff_upper] / 1e6, 1),
                round(s11_dB[idx_cutoff_upper], 1),
                round(np.real(Zin[idx_cutoff_upper]), 1),
            ),
            "color": "red",
            "ha": "left",
        },
        {
            "pos": (freq[idx] / 1e6, s11_dB[idx]),
            "offset": [2.0, 2.0],
            "text": " {} MHz: {} dB\n@ {} Ohm".format(
                round(freq[idx][0] / 1e6, 1), round(s11_dB[idx][0], 1), round(np.real(Zin[idx][0]), 1)
            ),
            "color": "blue",
            "ha": "left",
        },
    ]

    for marker in markers:
        pyplot.scatter(marker["pos"][0], marker["pos"][1], color=marker["color"], zorder=3)
        pyplot.text(
            marker["pos"][0] + marker["offset"][0],
            marker["pos"][1] + marker["offset"][1],
            marker["text"],
            ha=marker["ha"],
            zorder=4,
            fontweight="normal",
        )

pyplot.savefig('fig_reflection.svg')

#########################################################################################
# compute far-field from recording box and generate plots
#
if enable_nf2ff:
    # Calculate the far field at phi=0 degrees and at phi=90 degrees
    theta = np.arange(-180.0, 180.0, 1.0)
    phi = np.arange(-90, 90, 2)
    print("=" * 80)
    print("\n")
    print("Calculating the 3D far field...")

    # https://docs.openems.de/python/openEMS/nf2ff.html#openEMS.nf2ff.nf2ff.CalcNF2FF
    # CalcNF2FF(sim_path, freq, theta, phi, radius=1, center=[0, 0, 0], outfile=None, read_cached=False, verbose=0)

    # theta/phi – array like – Theta/Phi angles to calculate the far-field
    # radius – float – Radius to calculate the far-field (default is 1m)
    nf2ff_radius = nf_ff_transition_distance
    print("Analyzing far-field at radius {}".format(nf2ff_radius))

    # 1) Analyze far-field for: single center frequency of interest
    # Works!
    #
    # freqs_of_interest = [f0]
    #
    # Result:
    #    nf2ff: Analysing far-field for 1 frequencies.
    #    Radiated power: P_rad = 1.3781441597114614e-20 W
    #    Directivity: D_max = -42.66256438449489 dBi
    #    Efficiency: nu_rad = 101.85287356184361 %
    #    Theta_HPBW = 43.0 °

    # 2) Analyze far-field for: lower bound, center and upper bound frequency of interest
    # Works!
    #
    # freqs_of_interest = [446.0e6, 446.1e6, 446.2e6]
    #
    # Result:
    #    nf2ff: Analysing far-field for 3 frequencies.
    #    Radiated power: P_rad = 1.3763972766838116e-20 W
    #    Directivity: D_max = -42.662132139823896 dBi
    #    Efficiency: nu_rad = 101.76329904670399 %
    #    Theta_HPBW = 43.0 °

    # 3) Analyze far-field for: all frequencies with S11 at least -10 dB
    # Works!
    #
    idx_cutoff_lower = cutoff_dbs_results[cutoff_db_resonance]["lower"]["idx"]
    idx_cutoff_upper = cutoff_dbs_results[cutoff_db_resonance]["upper"]["idx"]
    freqs_of_interest = freq[idx_cutoff_lower: idx_cutoff_upper + 1]
    #
    # Result:
    #    nf2ff: Analysing far-field for 1206 frequencies.
    #    Radiated power: P_rad = 3.313485009786238e-21 W
    #    Directivity: D_max = -42.46238526982907 dBi
    #    Efficiency: nu_rad = 24.483622446993255 %
    #    Theta_HPBW = 43.0 °

    # 4) Analyze far-field for: all frequencies in excitation range [f0 - fc, f0 + fc]
    # Does NOT work!
    #
    # OOM killed! - "nf2ff: Analysing far-field for 2001 frequencies."
    #
    # freqs_of_interest = freq

    print("Analyzing far-field for {} frequencies:\n{}".format(len(freqs_of_interest), pformat(freqs_of_interest)))

    nf2ff_res = nf2ff.CalcNF2FF(
        sim_path=output_dir,
        freq=freqs_of_interest,
        theta=theta,
        phi=phi,
        radius=nf2ff_radius,
        read_cached=True,
        verbose=True,
    )

    Dmax_dB = 10 * np.log10(nf2ff_res.Dmax[0])
    E_norm = 20.0 * np.log10(nf2ff_res.E_norm[0] / np.max(nf2ff_res.E_norm[0])) + 10 * np.log10(nf2ff_res.Dmax[0])
    theta_HPBW = theta[np.where(np.squeeze(E_norm[:, phi == 0]) < Dmax_dB - 3)[0][0]]

    # Display power and directivity
    print("Radiated power: P_rad = {} W".format(nf2ff_res.Prad[0]))
    print("Directivity: D_max = {} dBi".format(Dmax_dB))
    print("Efficiency: nu_rad = {} %".format(100 * nf2ff_res.Prad[0] / np.interp(f0, freq, feed.P_acc)))
    print("Theta_HPBW = {} °".format(theta_HPBW))

    E_norm = 20.0 * np.log10(nf2ff_res.E_norm[0] / np.max(nf2ff_res.E_norm[0])) + 10 * np.log10(nf2ff_res.Dmax[0])
    E_CPRH = 20.0 * np.log10(np.abs(nf2ff_res.E_cprh[0]) / np.max(nf2ff_res.E_norm[0])) + 10 * np.log10(
        nf2ff_res.Dmax[0]
    )
    E_CPLH = 20.0 * np.log10(np.abs(nf2ff_res.E_cplh[0]) / np.max(nf2ff_res.E_norm[0])) + 10 * np.log10(
        nf2ff_res.Dmax[0]
    )

    # Plot the pattern
    pyplot.figure()
    pyplot.plot(theta, E_norm[:, phi == 0], "k-", linewidth=2, label="$|E|$")
    pyplot.plot(theta, E_CPRH[:, phi == 0], "g--", linewidth=2, label="$|E_{CPRH}|$")
    pyplot.plot(theta, E_CPLH[:, phi == 0], "r-.", linewidth=2, label="$|E_{CPLH}|$")
    pyplot.grid()
    pyplot.xlabel("Theta (deg)")
    pyplot.ylabel("Directivity (dBi)")
    pyplot.title("Frequency: {} GHz".format(nf2ff_res.freq[0] / 1e9))
    pyplot.legend()
    pyplot.savefig('fig_directivity.svg')

#########################################################################################
# show all plots
#
if enable_show_plots:
    pyplot.show()


#########################################################################################
#########################################################################################


def generatorFunc_DumpFF2VTK(farfield, t, a, filename):
    """
    Create `.vtk` file from openEMS far-field dump.

    @see https://github.com/thliebig/openEMS-Project/discussions/151

    :param farfield: 2D array of values of field
    :param t: theta angles in radians
    :param a: phi angles in radians
    :param filename: output file name
    :return:
    """

    with open(filename, "w") as outFile:
        outFile.write(f"# vtk DataFile Version 3.0\n")
        outFile.write(f"Structured Grid by python-interface of openEMS\n")
        outFile.write(f"ASCII\n")
        outFile.write(f"DATASET STRUCTURED_GRID\n")

        outFile.write(f"DIMENSIONS 1 {len(t)} {len(a)}\n")
        outFile.write(f"POINTS {len(t) * len(a)} double\n")

        for na in range(len(a)):
            for nt in range(len(t)):
                val1 = farfield[nt][na] * math.sin(t[nt]) * math.cos(a[na])
                val2 = farfield[nt][na] * math.sin(t[nt]) * math.sin(a[na])
                val3 = farfield[nt][na] * math.cos(t[nt])
                outFile.write(f"{val1} {val2} {val3}\n")

        outFile.write(f"\n\n")
        outFile.write(f"POINT_DATA {len(t) * len(a)}\n")
        outFile.write(f"SCALARS gain double 1\n")
        outFile.write(f"LOOKUP_TABLE default\n")
        for na in range(len(a)):
            for nt in range(len(t)):
                outFile.write(f"{farfield[nt][na]}\n")


#########################################################################################
# dump radiation field to vtk file
#
if enable_nf2ff:
    # Dump radiation field to vtk file
    #
    # AttributeError: 'nf2ff' object has no attribute 'P_rad'
    # AttributeError: 'nf2ff' object has no attribute 'Prad'
    #
    # directivity = nf2ff.P_rad[0]/nf2ff.Prad*4*pi
    # directivity = nf2ff.Prad[0] / nf2ff.Prad * 4 * math.pi
    # directivity_CPRH = np.abs(nf2ff.E_cprh[0]) ** 2 / np.max(nf2ff.E_norm[0][:]) ** 2 * nf2ff.Dmax[0]
    # directivity_CPLH = np.abs(nf2ff.E_cplh[0]) ** 2 / np.max(nf2ff.E_norm[0][:]) ** 2 * nf2ff.Dmax[0]

    # use E_norm, E_CPRH, E_CPLH defined above ^
    directivity = E_norm
    directivity_CPRH = E_CPRH
    directivity_CPLH = E_CPLH

    generatorFunc_DumpFF2VTK(directivity, nf2ff.theta, nf2ff.phi, os.path.join(output_dir, "3D_Pattern.vtk"))
    generatorFunc_DumpFF2VTK(directivity_CPRH, nf2ff.theta, nf2ff.phi, os.path.join(output_dir, "3D_Pattern_CPRH.vtk"))
    generatorFunc_DumpFF2VTK(directivity_CPLH, nf2ff.theta, nf2ff.phi, os.path.join(output_dir, "3D_Pattern_CPLH.vtk"))

    # AttributeError: 'nf2ff' object has no attribute 'Dmax'
    # E_far_normalized = E_norm / np.max(E_norm) * nf2ff.Dmax[0]
    E_far_normalized = E_norm / np.max(E_norm) * nf2ff_res.Dmax[0]

    generatorFunc_DumpFF2VTK(E_far_normalized, nf2ff.theta, nf2ff.phi,
                             os.path.join(output_dir, "3D_Pattern_E_norm.vtk"))
