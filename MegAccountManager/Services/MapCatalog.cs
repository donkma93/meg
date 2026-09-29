namespace MegAccountManager.Services;

public sealed record MapInfo(int Id, string Name, string Category)
{
    public string Display => $"{Id:000} — {Name}";
    public string Detail => string.IsNullOrWhiteSpace(Category) ? Display : $"{Display}  [{Category}]";
}

public static class MapCatalog
{
    // MEGAMU / MU-style world IDs used by client SceneIndex and World### paths.
    // Unknown live IDs still format as "World {id}".
    private static readonly Dictionary<int, MapInfo> Maps = CreateMaps();

    private static Dictionary<int, MapInfo> CreateMaps()
    {
        var items = new (int Id, string Name, string Category)[]
        {
            (0, "Lorencia", "Town"),
            (1, "Dungeon", "Field"),
            (2, "Devias", "Town"),
            (3, "Noria", "Town"),
            (4, "Lost Tower", "Field"),
            (5, "Exile", "Special"),
            (6, "Arena", "PvP"),
            (7, "Atlans", "Field"),
            (8, "Tarkan", "Field"),
            (9, "Devil Square", "Event"),
            (10, "Icarus", "Field"),
            (11, "Blood Castle 1", "Event"),
            (12, "Blood Castle 2", "Event"),
            (13, "Blood Castle 3", "Event"),
            (14, "Blood Castle 4", "Event"),
            (15, "Blood Castle 5", "Event"),
            (16, "Blood Castle 6", "Event"),
            (17, "Blood Castle 7", "Event"),
            (18, "Chaos Castle 1", "Event"),
            (19, "Chaos Castle 2", "Event"),
            (20, "Chaos Castle 3", "Event"),
            (21, "Chaos Castle 4", "Event"),
            (22, "Chaos Castle 5", "Event"),
            (23, "Chaos Castle 6", "Event"),
            (24, "Kalima 1", "Field"),
            (25, "Kalima 2", "Field"),
            (26, "Kalima 3", "Field"),
            (27, "Kalima 4", "Field"),
            (28, "Kalima 5", "Field"),
            (29, "Kalima 6", "Field"),
            (30, "Valley of Loren", "Field"),
            (31, "Land of Trials", "Field"),
            (32, "Devil Square", "Event"),
            (33, "Aida", "Field"),
            (34, "Crywolf", "Field"),
            (35, "Crywolf (occupied)", "Field"),
            (36, "Kalima 7", "Field"),
            (37, "Kanturu Remains", "Field"),
            (38, "Kanturu Ruins", "Field"),
            (39, "Kanturu Relics", "Field"),
            (40, "Silent Map", "Special"),
            (41, "Barracks of Balgass", "Field"),
            (42, "Balgass Refuge", "Field"),
            (45, "Illusion Temple 1", "Event"),
            (46, "Illusion Temple 2", "Event"),
            (47, "Illusion Temple 3", "Event"),
            (48, "Illusion Temple 4", "Event"),
            (49, "Illusion Temple 5", "Event"),
            (50, "Illusion Temple 6", "Event"),
            (51, "Elbeland", "Town"),
            (52, "Blood Castle 8", "Event"),
            (53, "Chaos Castle 7", "Event"),
            (56, "Swamp of Calmness", "Field"),
            (57, "Raklion", "Field"),
            (58, "Raklion Boss", "Boss"),
            (62, "Santa Village", "Event"),
            (63, "Vulcanus", "Field"),
            (64, "Duel Arena", "PvP"),
            (65, "Doppleganger Snow", "Event"),
            (66, "Doppleganger Vulcanus", "Event"),
            (67, "Doppleganger Sea", "Event"),
            (68, "Doppleganger Crimson", "Event"),
            (69, "Imperial Guardian 1", "Event"),
            (70, "Imperial Guardian 2", "Event"),
            (71, "Imperial Guardian 3", "Event"),
            (72, "Imperial Guardian 4", "Event"),
            (79, "Loren Market", "Town"),
            (80, "Karutan 1", "Field"),
            (81, "Karutan 2", "Field"),
            (82, "Renewal Aida", "Field"),
            (83, "Crywolf Renewal", "Field"),
            (91, "Acheron", "Field"),
            (92, "Acheron (Alt)", "Field"),
            (95, "Debenter", "Field"),
            (96, "Debenter (Alt)", "Field"),
            (97, "Chaos Castle Survival", "Event"),
            (98, "Illusion Temple League 1", "Event"),
            (99, "Illusion Temple League 2", "Event"),
            (100, "Uruk Mountain", "Field"),
            (101, "Uruk Mountain (Alt)", "Field"),
            (102, "Tormented Square", "Event"),
            (103, "Tormented Square 1", "Event"),
            (104, "Tormented Square 2", "Event"),
            (105, "Tormented Square 3", "Event"),
            (106, "Tormented Square 4", "Event"),
            (110, "Nars", "Field"),
            (112, "Ferea", "Field"),
            (113, "Nixies Lake", "Field"),
            (114, "The Labyrinth", "Event"),
            (115, "Deep Dungeon 1", "Field"),
            (116, "Swamp of Darkness", "Field"),
            (117, "Kubera Mine", "Field"),
            (118, "Kubera Mine 2", "Field"),
            (119, "Kubera Mine 3", "Field"),
            (120, "Kubera Mine 4", "Field"),
            (121, "Kubera Mine 5", "Field"),
            (122, "Abyss of Atlans 1", "Field"),
            (123, "Abyss of Atlans 2", "Field"),
            (124, "Abyss of Atlans 3", "Field"),
            (125, "Scorched Canyon", "Field"),
            (126, "Red Smoke Icarus", "Field"),
            (127, "Arenil Temple", "Field"),
            (128, "Ashy Aida", "Field"),
            (129, "Grow Lancer Tutorial", "Special"),
            (131, "Blaze Kethotum", "Field"),
            (132, "Kanturu Undergrounds", "Field"),
            (133, "Ignis Volcano", "Field"),
            (134, "Boss Battle", "Boss"),
            (135, "Waterworld Atlans", "Field"),
            (136, "Swamp of Darkness (Alt)", "Field"),
            (137, "Crimson Icarus", "Field"),
        };

        var map = new Dictionary<int, MapInfo>(items.Length);
        foreach (var (id, name, category) in items)
        {
            map[id] = new MapInfo(id, name, category);
        }

        return map;
    }

    public static IReadOnlyList<MapInfo> GetAll() =>
        Maps.Values.OrderBy(m => m.Id).ToList();

    public static IReadOnlyList<MapInfo> Search(string? query)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            return GetAll();
        }

        var q = query.Trim();
        return Maps.Values
            .Where(m =>
                m.Id.ToString().Contains(q, StringComparison.OrdinalIgnoreCase) ||
                m.Name.Contains(q, StringComparison.OrdinalIgnoreCase) ||
                m.Category.Contains(q, StringComparison.OrdinalIgnoreCase) ||
                m.Display.Contains(q, StringComparison.OrdinalIgnoreCase))
            .OrderBy(m => m.Id)
            .ToList();
    }

    public static bool TryGet(int mapId, out MapInfo info) => Maps.TryGetValue(mapId, out info!);

    public static bool IsKnown(int? mapId) => mapId is not null && Maps.ContainsKey(mapId.Value);

    public static string GetName(int? mapId)
    {
        if (mapId is null)
        {
            return string.Empty;
        }

        return Maps.TryGetValue(mapId.Value, out var info)
            ? info.Name
            : $"World {mapId.Value}";
    }

    public static string Format(int? mapId)
    {
        if (mapId is null)
        {
            return string.Empty;
        }

        return Maps.TryGetValue(mapId.Value, out var info)
            ? $"{info.Name} ({mapId.Value})"
            : $"World {mapId.Value}";
    }

    public static string FormatDetail(int? mapId)
    {
        if (mapId is null)
        {
            return string.Empty;
        }

        return Maps.TryGetValue(mapId.Value, out var info)
            ? info.Detail
            : $"World {mapId.Value}  [Unknown]";
    }
}
