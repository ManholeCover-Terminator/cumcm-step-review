function outputs = export_publication_figure(fig, outputStem, dpi, grayscalePreview, svg, strictDesign)
%EXPORT_PUBLICATION_FIGURE 通过设计门禁后默认只输出一个 300 DPI PNG。
%svg=true 时追加 SVG；grayscalePreview=true 时追加灰度质检图。
arguments
    fig (1,1) matlab.ui.Figure
    outputStem (1,1) string
    dpi (1,1) double {mustBeInteger,mustBeGreaterThanOrEqual(dpi,300)} = 300
    grayscalePreview (1,1) logical = false
    svg (1,1) logical = false
    strictDesign (1,1) logical = true
end

[folder, name, ~] = fileparts(outputStem);
if strlength(folder) == 0
    folder = ".";
end
if ~isfolder(folder)
    mkdir(folder);
end
stem = fullfile(folder, name);
pngPath = stem + ".png";
fig.PaperPositionMode = "auto";
drawnow;
designIssues = audit_publication_figure(fig);
if strictDesign && ~isempty(designIssues)
    error("出版设计预检未通过：%s", join(designIssues, "；"));
end
exportgraphics(fig, pngPath, "Resolution", dpi);
outputs = struct("png", pngPath);
if svg
    svgPath = stem + ".svg";
    exportgraphics(fig, svgPath, "ContentType", "vector");
    outputs.svg = svgPath;
end
if grayscalePreview
    qaFolder = fullfile(folder, "_qa");
    if ~isfolder(qaFolder)
        mkdir(qaFolder);
    end
    image = imread(pngPath);
    rgb = double(image(:,:,1:3));
    if isinteger(image)
        rgb = rgb / double(intmax(class(image)));
    end
    gray = 0.2126 * rgb(:,:,1) + 0.7152 * rgb(:,:,2) + 0.0722 * rgb(:,:,3);
    grayPath = fullfile(qaFolder, name + "_grayscale.png");
    imwrite(gray, grayPath);
    outputs.grayscale = grayPath;
end
end
