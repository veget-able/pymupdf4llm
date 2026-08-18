# PBChart63 live native-HF evaluation on RTX 5070 Ti

Date: 2026-08-18

Status: completed

## Result

The `chart/finder-pbchart63-v1` branch exceeded 0.63 macro in a live
end-to-end evaluation on the `ai-70ti` hardware/software stack.

| Metric | Result |
|---|---:|
| ParseBench Chart pages | 568 / 568 |
| Failed pages | 0 |
| Evaluated rules | 4,864 |
| Passed rules | 3,007 |
| Macro | **0.6327847768428755** |
| Micro | **0.6182154605263158** |
| D0 chart detections | 907 |
| Native-HF crop calls | 907 |
| Serialized chart tables | 907 |

This is a hardware/software-specific result. It is not claimed to reproduce
bit-for-bit on a different GPU, CPU, operating system, or inference-library
stack. Model comparisons must use a base control measured in the same
environment.

## Live evaluation contract

- PyMuPDF4LLM branch: `chart/finder-pbchart63-v1`
- Evaluated product commit:
  `cb83c8da4eaf2fb3bf6ff08923ba408b8836321f`
- `src/helpers/chart_layout.py` SHA-256:
  `1be5db0665be877f36938eaa94bc683f796e1c0b6e11a0c8de1bcdc8d57916ca`
- PaddleOCR-VL model: `PaddlePaddle/PaddleOCR-VL-1.6`
- Model revision: `66317acc4c9fc17bd154591ce650735cd2855f3e`
- Model weight SHA-256:
  `85a479d506a11e724e7285d395c551be69f41dbc16b6342d3cacfb189aed71db`
- Production D0 detector SHA-256:
  `18f1df3ddba43bfdf741f86d16b0ba04080a9f40cbb47a3f25f7da1a059c0b7e`
- ParseBench fixture `chart.jsonl` SHA-256:
  `82eb2d660b286a5e1b8bd57f3f159a722b13849834561211dc1ccd5c5a39582b`
- ParseBench version/commit: `0.2.0` /
  `ffbddcd33315f6a7e0836e2b5b4808b4af35abdf`
- Backend: native Hugging Face Transformers, greedy decoding
- vLLM: not used
- Cached detector results, crops, VLM outputs, and Markdown: not used

The run opened all 568 source PDFs, ran the D0 detector, expanded each
detector box by two PDF points, invoked the native-HF PaddleOCR-VL callback,
applied the leading-blank header correction and pipe normalization, converted
only generated chart payload tables to HTML, removed only text spans at least
90% contained by a successfully extracted detector box, serialized the final
Markdown, and then ran ParseBench.

## Hardware and software scope

- Host: `ai-70ti`
- OS/kernel: Ubuntu 24.04.3 LTS / Linux 7.0.0-28-generic
- CPU: AMD Ryzen 9 9900X, 12 cores / 24 threads
- GPU: 2 x NVIDIA GeForce RTX 5070 Ti, 16,303 MiB each
- NVIDIA driver / reported CUDA: 580.173.02 / 13.0
- Python: 3.12.3
- PyTorch / CUDA / cuDNN: 2.11.0+cu130 / 13.0 / 9.19.0
- Transformers: 5.12.1
- PyMuPDF / MuPDF / PyMuPDF-Layout / PyMuPDF4LLM: 1.28.2
- ONNX Runtime: 1.28.0, `CPUExecutionProvider`
- markdown2: 2.5.5

The D0 detector and ParseBench scorer ran on the host CPU. Two native-HF
PaddleOCR-VL processes ran as one shard per 5070 Ti GPU.

## Evidence integrity and recovery note

- Formal ParseBench report SHA-256:
  `557f2878f76281f6c93be81c345354855663826ce0a036870ac2b382e1eb30b6`
- Sorted 568-result manifest SHA-256:
  `b83c62fcd6158700f424c182c3af379398cc7552790dddf35ef8bd8f377f7552`
- Live result creation interval:
  2026-08-18 12:18:59–12:34:17 KST

The first scoring command failed before scoring because an old ParseBench
wrapper referenced a removed Python interpreter. On recovery, the runner
recognized and skipped all 568 atomic result files, and ParseBench scored those
preserved live results. The recovery entry overwrote two shard summary files
with `completed=0, skipped=284`, but it did not rewrite a result file or rerun
detector/VLM inference. The rewritten summaries must not be used as an
inference-speed record; this does not affect the quality score above.

## Clarification of the original commit validation

The original `cb83c8d` commit message reports macro `0.6316110679226876`,
micro `0.6178042763157895`, and 3,005/4,864 passed rules. That number remains a
valid cached-output policy audit, but its final policy-audit stage did not
rerun detector or VLM inference. It must not be described as the live
final-branch score.

The later result recorded in this document is distinct: it ran the final
branch from the source PDFs without cached intermediate outputs and obtained
macro `0.6327847768428755` and 3,007/4,864 passed rules. No production D0 model,
service, route, or deployment pointer was changed by the evaluation.
