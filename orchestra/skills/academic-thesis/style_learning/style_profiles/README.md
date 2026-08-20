# Style Profiles 目录

此目录存放通过 `style_analyzer.py` 从范文中提取的 Style Profile JSON 文件。

## 使用方法

```bash
cd style_learning/
python style_analyzer.py ../path/to/sample_paper.txt style_profiles/my_profile.json
```

## 文件命名

建议使用描述性名称，如：
- `ieee_journal.json`
- `advisor_zhang.json`
- `target_conference.json`

每个 JSON 文件遵循 `style_extractor.md` 中定义的 Schema。
