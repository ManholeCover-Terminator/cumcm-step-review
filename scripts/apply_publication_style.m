function style = apply_publication_style(fig, language, widthProfile, journal)
%APPLY_PUBLICATION_STYLE 为数学建模论文图应用统一出版样式。
%   journal 可选 nature/science/cell/ieee/general/okabe_ito/wong，默认 nature。
%   与 Python 侧 plot_style.py 的 JOURNAL_PALETTES 保持同一套色板。
%   Python 侧的 variants 变体（冷色板/珊瑚红板/莫兰迪板/大地色板等）以
%   plot_style.py 为准；MATLAB 侧固定使用各期刊默认主色板。
arguments
    fig (1,1) matlab.ui.Figure
    language (1,1) string {mustBeMember(language,["zh","en"])} = "zh"
    widthProfile (1,1) string {mustBeMember(widthProfile,["single","double","report","cumcm"])} = "report"
    journal (1,1) string {mustBeMember(journal,["nature","science","cell","ieee","general","okabe_ito","wong"])} = "nature"
end

widths = struct("single", 3.5, "double", 7.2, "report", 6.3, "cumcm", 5.9);
fontName = chooseFont(language);
journalColors = struct( ...
    "nature", [ ...
        0.0588 0.4196 0.7412
        0.9490 0.4353 0.1294
        0.6196 0.7922 0.8824
        0.0314 0.2353 0.3725
        0.4980 0.5490 0.5529 ], ...
    "science", [ ...
        0.8941 0.0980 0.2157
        0.6392 0.1020 0.1882
        0.1843 0.4314 0.7098
        0.5608 0.7569 0.8824
        0.5608 0.5608 0.5608 ], ...
    "cell", [ ...
        0.1176 0.5176 0.2863
        0.0941 0.3804 0.2196
        0.5098 0.8784 0.6667
        0.5569 0.2667 0.6784
        0.3373 0.3961 0.4510 ], ...
    "okabe_ito", [ ...
        0.9020 0.6235 0.0000
        0.3373 0.7059 0.9137
        0.0000 0.6196 0.4510
        0.9412 0.8941 0.2588
        0.0000 0.4471 0.6980
        0.8353 0.3686 0.0000
        0.8000 0.4745 0.6549
        0.6000 0.6000 0.6000 ], ...
    "wong", [ ...
        0.0000 0.4667 0.7333
        0.9333 0.4667 0.2000
        0.2000 0.7333 0.9333
        0.8000 0.2000 0.0667
        0.0000 0.6000 0.5333
        0.7333 0.7333 0.7333 ], ...
    "ieee", [ ...
        0.0000 0.4471 0.7412
        0.8510 0.3255 0.0980
        0.9294 0.6941 0.1255
        0.4941 0.1843 0.5569
        0.4667 0.6745 0.1882
        0.3020 0.7451 0.9333
        0.6353 0.0784 0.1843 ], ...
    "general", [ ...
        0.1216 0.4667 0.7059
        1.0000 0.4980 0.0549
        0.1725 0.6275 0.1725
        0.8392 0.1529 0.1569
        0.5804 0.4039 0.7412
        0.5490 0.3373 0.2941
        0.8902 0.4667 0.7608
        0.4980 0.4980 0.4980 ] );
colors = journalColors.(journal);

widthIn = widths.(widthProfile);
fig.Units = "inches";
fig.Position(3:4) = [widthIn, widthIn * 0.62];
fig.Color = "white";
set(fig, "DefaultAxesFontName", fontName, ...
    "DefaultAxesFontSize", 9.5, ...
    "DefaultAxesLineWidth", 0.7, ...
    "DefaultAxesTitleFontSizeMultiplier", 1.0, ...
    "DefaultAxesTitleFontWeight", "normal", ...
    "DefaultAxesLabelFontSizeMultiplier", 1.0, ...
    "DefaultAxesColorOrder", colors, ...
    "DefaultLineLineWidth", 1.1, ...
    "DefaultLineMarkerSize", 3.5, ...
    "DefaultLegendBox", "off");

axesList = findall(fig, "Type", "axes");
for k = 1:numel(axesList)
    axesList(k).FontName = fontName;
    axesList(k).FontSize = 9.5;
    axesList(k).LineWidth = 0.7;
    axesList(k).TitleFontSizeMultiplier = 1.0;
    axesList(k).TitleFontWeight = "normal";
    axesList(k).LabelFontSizeMultiplier = 1.0;
    axesList(k).ColorOrder = colors;
    axesList(k).Box = "off";
    grid(axesList(k), "off");
end

style = struct("font", fontName, "colors", colors, ...
    "sizeInches", [widthIn, widthIn * 0.62]);
end

function fontName = chooseFont(language)
fonts = string(listfonts);
if language == "zh"
    candidates = ["Noto Sans CJK SC","Source Han Sans SC", ...
        "Microsoft YaHei","SimHei","PingFang SC"];
else
    candidates = ["Arial","Helvetica","Times New Roman"];
end
fontName = "Helvetica";
for candidate = candidates
    if any(strcmpi(fonts, candidate))
        fontName = candidate;
        return;
    end
end
warning("未找到首选字体，导出后必须检查中文与特殊符号是否缺字。");
end
