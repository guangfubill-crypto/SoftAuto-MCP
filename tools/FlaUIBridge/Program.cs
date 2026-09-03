using System.Drawing;
using System.Text.Json;
using FlaUI.Core.AutomationElements;
using FlaUI.Core.Definitions;
using FlaUI.Core;
using FlaUI.UIA2;
using FlaUI.UIA3;

const string Empty = "";
var options = new JsonSerializerOptions { WriteIndented = false };

while (Console.ReadLine() is { } line)
{
    try
    {
        using var document = JsonDocument.Parse(line);
        var request = document.RootElement;
        var operation = request.TryGetProperty("op", out var op) ? op.GetString() : null;
        if (operation != "inspect_point")
        {
            throw new InvalidOperationException("Unsupported operation");
        }

        var x = request.GetProperty("x").GetInt32();
        var y = request.GetProperty("y").GetInt32();
        var requestedEngine = request.TryGetProperty("engine", out var engine)
            ? engine.GetString()?.ToLowerInvariant()
            : "auto";
        var engines = requestedEngine switch
        {
            "uia2" => new[] { "uia2" },
            "uia3" => new[] { "uia3" },
            _ => new[] { "uia3", "uia2" },
        };

        Dictionary<string, object?>? result = null;
        Exception? lastError = null;
        foreach (var selectedEngine in engines)
        {
            try
            {
                using var automation = selectedEngine == "uia2"
                    ? (AutomationBase)new UIA2Automation()
                    : new UIA3Automation();
                var element = automation.FromPoint(new Point(x, y));
                if (element is null)
                {
                    throw new InvalidOperationException("No element at point");
                }
                result = Inspect(element, selectedEngine, x, y);
                break;
            }
            catch (Exception exception)
            {
                lastError = exception;
            }
        }

        if (result is null)
        {
            throw lastError ?? new InvalidOperationException("No UIA engine resolved the point");
        }
        Console.WriteLine(JsonSerializer.Serialize(result, options));
    }
    catch (Exception exception)
    {
        Console.WriteLine(JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["ok"] = false,
            ["error"] = exception.Message,
        }, options));
    }
}

static Dictionary<string, object?> Inspect(AutomationElement element, string engine, int x, int y)
{
    var chain = new List<Dictionary<string, object?>>();
    var current = element;
    for (var depth = 0; current is not null && depth < 64; depth++)
    {
        chain.Add(Descriptor(current));
        current = current.Parent;
    }
    chain.Reverse();
    var window = chain.Count > 0 ? chain[0] : Descriptor(element);
    var path = chain.Count > 2 ? chain.Skip(1).Take(chain.Count - 2).ToList() : new List<Dictionary<string, object?>>();
    var target = Descriptor(element);
    return new Dictionary<string, object?>
    {
        ["ok"] = true,
        ["engine"] = engine,
        ["point"] = new Dictionary<string, int> { ["x"] = x, ["y"] = y },
        ["window"] = window,
        ["path"] = path,
        ["target"] = target,
        ["locator"] = new Dictionary<string, object?>
        {
            ["backend"] = "windows-uia",
            ["version"] = 1,
            ["window"] = window,
            ["path"] = path,
            ["target"] = target,
            ["capture_engine"] = $"flaui-{engine}",
        },
    };
}

static Dictionary<string, object?> Descriptor(AutomationElement element)
{
    var controlType = element.Properties.ControlType.ValueOrDefault;
    var rectangle = element.Properties.BoundingRectangle.ValueOrDefault;
    return new Dictionary<string, object?>
    {
        ["automation_id"] = element.Properties.AutomationId.ValueOrDefault ?? Empty,
        ["name"] = element.Properties.Name.ValueOrDefault ?? Empty,
        ["class_name"] = element.Properties.ClassName.ValueOrDefault ?? Empty,
        ["control_type"] = controlType == ControlType.Unknown ? Empty : $"{controlType}Control",
        ["framework_id"] = element.Properties.FrameworkId.ValueOrDefault ?? Empty,
        ["process_id"] = element.Properties.ProcessId.ValueOrDefault,
        ["native_window_handle"] = element.Properties.NativeWindowHandle.ValueOrDefault.ToInt64(),
        ["bounds"] = new Dictionary<string, int>
        {
            ["left"] = rectangle.Left,
            ["top"] = rectangle.Top,
            ["right"] = rectangle.Right,
            ["bottom"] = rectangle.Bottom,
            ["width"] = rectangle.Width,
            ["height"] = rectangle.Height,
        },
    };
}
