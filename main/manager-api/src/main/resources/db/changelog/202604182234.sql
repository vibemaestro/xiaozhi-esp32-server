-- Add Vieneu TTS provider
DELETE FROM `ai_model_provider` WHERE id = 'SYSTEM_TTS_Vieneu';
INSERT INTO `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) VALUES
('SYSTEM_TTS_Vieneu', 'TTS', 'vieneu', 'Vieneu Vietnamese TTS', '[{"key":"api_key","label":"API Key","type":"string"},{"key":"voice","label":"Voice ID","type":"string"},{"key":"speed","label":"Speed","type":"number"},{"key":"output_dir","label":"Output Directory","type":"string"}]', 25, 1, NOW(), 1, NOW());

DELETE FROM `ai_model_config` WHERE id = 'TTS_Vieneu';
INSERT INTO `ai_model_config` VALUES ('TTS_Vieneu', 'TTS', 'Vieneu', 'Vieneu Vietnamese TTS', 0, 1, '{"type": "vieneu", "api_key": "", "voice": "vi-VN", "speed": 1.0, "output_dir": "tmp/"}', 'https://vieneu.com', 'Vieneu Vietnamese Text-to-Speech service', 25, NULL, NULL, NULL, NULL);

-- Add ValtecTTS TTS provider
DELETE FROM `ai_model_provider` WHERE id = 'SYSTEM_TTS_ValtecTTS';
INSERT INTO `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) VALUES
('SYSTEM_TTS_ValtecTTS', 'TTS', 'valtec', 'ValtecTTS Vietnamese TTS', '[{"key":"api_key","label":"API Key","type":"string"},{"key":"voice","label":"Voice ID","type":"string"},{"key":"speed","label":"Speed","type":"number"},{"key":"volume","label":"Volume","type":"number"},{"key":"output_dir","label":"Output Directory","type":"string"}]', 26, 1, NOW(), 1, NOW());

DELETE FROM `ai_model_config` WHERE id = 'TTS_ValtecTTS';
INSERT INTO `ai_model_config` VALUES ('TTS_ValtecTTS', 'TTS', 'ValtecTTS', 'ValtecTTS Vietnamese TTS', 0, 1, '{"type": "valtec", "api_key": "", "voice": "vi-VN", "speed": 1.0, "volume": 0, "output_dir": "tmp/"}', 'https://valtec.vn', 'ValtecTTS Vietnamese Text-to-Speech service', 26, NULL, NULL, NULL, NULL);
