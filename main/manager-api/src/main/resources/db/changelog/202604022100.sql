-- Add Gipformer Vietnamese speech recognition service configuration
delete from `ai_model_provider` where id = 'SYSTEM_ASR_GipformerASR';
INSERT INTO `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) VALUES
('SYSTEM_ASR_GipformerASR', 'ASR', 'gipformer', 'Gipformer Vietnamese speech recognition', '[{"key":"quantize","label":"Precision mode","type":"string"},{"key":"output_dir","label":"Output directory","type":"string"},{"key":"num_threads","label":"Number of inference threads","type":"number"},{"key":"decoding_method","label":"Decoding method","type":"string"}]', 19, 1, NOW(), 1, NOW());

delete from `ai_model_config` where id = 'ASR_GipformerASR';
INSERT INTO `ai_model_config` VALUES ('ASR_GipformerASR', 'ASR', 'GipformerASR', 'Gipformer Vietnamese speech recognition', 0, 1, '{"type": "gipformer", "quantize": "int8", "output_dir": "tmp/", "num_threads": 2, "decoding_method": "greedy_search"}', 'https://huggingface.co/g-group-ai-lab/gipformer-65M-rnnt', 'The Gipformer 65M RNNT Vietnamese speech recognition model supports fp32 and int8 precision and is automatically downloaded from HuggingFace.', 22, NULL, NULL, NULL, NULL);

-- Documentation on updating Gipformer ASR model configuration
UPDATE `ai_model_config` SET
`doc_link` = 'https://huggingface.co/g-group-ai-lab/gipformer-65M-rnnt',
`remark` = 'Gipformer Vietnamese Speech Recognition Configuration Instructions:

1. Gipformer is a Vietnamese speech recognition model based on the RNNT architecture (65M parameters).

2. The model will be automatically downloaded from HuggingFace; manual download is not required.

3. Precision Mode (quantize):

- fp32: Full precision, best recognition results but slower speed.

- int8: Quantization mode, smaller size and faster speed (recommended).

4. Number of Inference Threads (num_threads): Controls the number of CPU inference threads; 2-4 is recommended.

5. Decoding Method (decoding_method):

- greedy_search: Greedy search, faster speed (recommended).

- modified_beam_search: Beam search, higher precision but slower speed.
' WHERE `id` = 'ASR_GipformerASR';
