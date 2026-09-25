using BurningTertium.Installer.Core;
using System.Security.Cryptography;
using System.Text.Json;

var workspace = args.Length == 2 && args[0] == "--workspace"
    ? Path.GetFullPath(args[1]) : FindWorkspace(AppContext.BaseDirectory);
var mod = Path.Combine(workspace, "mods", "active", "BurningTertium");
var output = Path.Combine(mod, "payload");
var specs = Sources(workspace, mod).OrderBy(spec => spec.Id, StringComparer.Ordinal).ToArray();
var duplicateIds = specs.GroupBy(spec => spec.Id, StringComparer.Ordinal).Where(group => group.Count() != 1).Select(group => group.Key).ToArray();
var duplicateTargets = specs.GroupBy(spec => spec.Target, StringComparer.OrdinalIgnoreCase).Where(group => group.Count() != 1).Select(group => group.Key).ToArray();
if (duplicateIds.Length != 0 || duplicateTargets.Length != 0)
    throw new InvalidDataException($"Duplicate payload identities. IDs: {string.Join(", ", duplicateIds)}; targets: {string.Join(", ", duplicateTargets)}");
var blockers = new List<object>();
foreach (var spec in specs)
{
    Check(spec.OutputSource, spec.OutputSize, spec.OutputHash, spec.Id + " output", blockers);
    if (spec.BaseSource is not null) Check(spec.BaseSource, spec.BaseSize, spec.BaseHash!, spec.Id + " base", blockers);
}
if (blockers.Count != 0)
{
    Directory.CreateDirectory(output);
    File.WriteAllText(Path.Combine(output, "blockers.json"),
        JsonSerializer.Serialize(new { status = "blocked", blockers }, Safety.Json) + "\n");
    Console.Error.WriteLine($"Payload generation blocked by {blockers.Count} unauthenticated or missing source(s).");
    return 2;
}

if (Directory.Exists(output)) Directory.Delete(output, true);
Directory.CreateDirectory(Path.Combine(output, "inserts"));
var manifest = new PayloadManifest();
foreach (var spec in specs)
{
    var basis = spec.BaseSource is null ? null : File.ReadAllBytes(spec.BaseSource);
    var desired = File.ReadAllBytes(spec.OutputSource);
    var (operations, inserts) = BuildDelta(basis, desired);
    VerifyDelta(spec.Id, basis, inserts, operations, desired);
    var payloadRelative = "inserts/" + spec.Id + ".bin";
    var payloadPath = Path.Combine(output, payloadRelative.Replace('/', Path.DirectorySeparatorChar));
    File.WriteAllBytes(payloadPath, inserts);
    manifest.Files.Add(new FileRecipe
    {
        Id = spec.Id, Target = spec.Target, Base = spec.BaseTarget, BaseSize = spec.BaseSize,
        BaseSha256 = spec.BaseHash, OutputSize = desired.LongLength, OutputSha256 = Hash(desired),
        Payload = payloadRelative, PayloadSize = inserts.LongLength, PayloadSha256 = Hash(inserts),
        Addition = spec.Addition, Operations = operations
    });
}
File.WriteAllText(Path.Combine(output, "manifest.json"),
    JsonSerializer.Serialize(manifest, Safety.Json).Replace("\r\n", "\n", StringComparison.Ordinal) + "\n");
Console.WriteLine($"Generated {manifest.Files.Count} authenticated recipes in {output}");
return 0;

static (List<DeltaOperation>, byte[]) BuildDelta(byte[]? basis, byte[] desired)
{
    if (basis is null)
        return (new List<DeltaOperation> { new() { Kind = DeltaKind.Insert, Offset = 0, Count = desired.Length } }, desired);
    const int block = 256;
    var index = new Dictionary<ulong, List<int>>();
    for (var offset = 0; offset + block <= basis.Length; offset += 16)
    {
        var key = Fingerprint(basis.AsSpan(offset, block));
        if (!index.TryGetValue(key, out var offsets)) index[key] = offsets = new List<int>();
        if (offsets.Count < 128) offsets.Add(offset);
    }
    var operations = new List<DeltaOperation>();
    using var inserts = new MemoryStream();
    var pendingStart = 0;
    var pendingCount = 0;
    void FlushInsert()
    {
        if (pendingCount == 0) return;
        operations.Add(new DeltaOperation { Kind = DeltaKind.Insert, Offset = pendingStart, Count = pendingCount });
        pendingCount = 0;
    }
    for (var position = 0; position < desired.Length;)
    {
        var bestOffset = -1;
        var bestLength = 0;
        if (position + block <= desired.Length && index.TryGetValue(Fingerprint(desired.AsSpan(position, block)), out var candidates))
        {
            foreach (var candidate in candidates)
            {
                var length = 0;
                while (candidate + length < basis.Length && position + length < desired.Length &&
                       basis[candidate + length] == desired[position + length]) length++;
                if (length > bestLength) { bestOffset = candidate; bestLength = length; }
            }
        }
        if (bestLength >= block)
        {
            FlushInsert();
            operations.Add(new DeltaOperation { Kind = DeltaKind.Copy, Offset = bestOffset, Count = bestLength });
            position += bestLength;
        }
        else
        {
            if (pendingCount == 0) pendingStart = checked((int)inserts.Position);
            inserts.WriteByte(desired[position++]);
            pendingCount++;
        }
    }
    FlushInsert();
    return (operations, inserts.ToArray());
}

static ulong Fingerprint(ReadOnlySpan<byte> bytes)
{
    const ulong basis = 14695981039346656037;
    const ulong prime = 1099511628211;
    var value = basis;
    foreach (var item in bytes) { value ^= item; value *= prime; }
    return value;
}

static void VerifyDelta(string id, byte[]? basis, byte[] inserts, IEnumerable<DeltaOperation> operations, byte[] expected)
{
    using var actual = new MemoryStream();
    foreach (var operation in operations)
    {
        var source = operation.Kind == DeltaKind.Copy ? basis : inserts;
        if (source is null || operation.Offset < 0 || operation.Count < 0 || operation.Offset + operation.Count > source.Length)
            throw new InvalidDataException("Invalid generated operation for " + id);
        actual.Write(source, checked((int)operation.Offset), operation.Count);
    }
    if (!actual.ToArray().AsSpan().SequenceEqual(expected))
        throw new InvalidDataException("Generated delta replay differs for " + id);
}

static void Check(string path, long size, string hash, string label, List<object> blockers)
{
    if (!File.Exists(path)) { blockers.Add(new { component = label, path, reason = "missing" }); return; }
    var actualSize = new FileInfo(path).Length;
    var actualHash = Safety.Hash(path);
    if (actualSize != size || !actualHash.Equals(hash, StringComparison.OrdinalIgnoreCase))
        blockers.Add(new { component = label, path, reason = "identity-mismatch", expectedSize = size,
            actualSize, expectedSha256 = hash, actualSha256 = actualHash });
}

static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

static string FindWorkspace(string start)
{
    for (var directory = new DirectoryInfo(start); directory is not null; directory = directory.Parent)
        if (Directory.Exists(Path.Combine(directory.FullName, "mods", "active", "BurningTertium"))) return directory.FullName;
    throw new InvalidOperationException("Workspace root was not found. Use --workspace <path>.");
}

static IEnumerable<SourceSpec> Sources(string root, string mod)
{
    // Stock inputs are the SHA-pinned backups taken before the first local trial; outputs are the
    // in-game-tested red materials. Both live in the ignored analysis/ tree and never enter Git.
    string A(string relative) => Path.Combine(mod, "analysis", relative.Replace('/', Path.DirectorySeparatorChar));
    const string stock = "local-red-trial-20260923T203209Z-d11ff686/";
    yield return new("hologram", "bundle/data/ba/bacd9b3be2a4c57f",
        A(stock + "hologram.original"), 114360, "e0d63444385473b9b4e299318cd3fdc85e2188f9df9da06ab2224a41654cb616",
        A("red-holo-main-material-24735202/hologram.material.candidate"), 133912,
        "5d1fcc93ee8e9e951ab874ddd1298751cb6c157b528090652cfdfcd3d0850250", false, "bundle/data/ba/bacd9b3be2a4c57f");
    yield return new("hologram-side", "bundle/data/97/97b5490a85966a77",
        A(stock + "hologram_side.original"), 133988, "28a94fa9b2a988d8dd93925c40e4687091b6e766f57d1c283eab9fddbaa03a03",
        A("red-material-trial-24735202/hologram_side.material.candidate"), 133988,
        "6541de8e29cda29a996d7580020468df6360794187017f824c9418b20cd8df21", false, "bundle/data/97/97b5490a85966a77");
    yield return new("hologram-bottom", "bundle/data/51/51f7e0e66641669b",
        A(stock + "hologram_bottom.original"), 84848, "078ed294f4bab50fa984a035d9c94da4e5521da858c148cc52316f5fcfe448e8",
        A("red-material-trial-24735202/hologram_bottom.material.candidate"), 84848,
        "3250e754ac19c8f8a8b24c4194e13e1c9eb607d86254d1a933423d1935e83351", false, "bundle/data/51/51f7e0e66641669b");
    yield return new("hologram-grid", "bundle/data/59/59c4260bff372016",
        A(stock + "hologram_grid.original"), 217128, "c49cba30643a8c863c2818df51bbf5f761f7dc0cd32c4912b3d51d037e655db4",
        A("red-grid-material-24735202/hologram_grid.material.candidate"), 275960,
        "eed51d396ea8f0a13c151d303b79e4f4ccc6dab82051a2172c23deaad84ae4d7", false, "bundle/data/59/59c4260bff372016");
    foreach (var relative in new[] { "BurningTertium.mod", "scripts/mods/BurningTertium/BurningTertium.lua",
                 "scripts/mods/BurningTertium/BurningTertium_data.lua",
                 "scripts/mods/BurningTertium/BurningTertium_localization.lua",
                 "scripts/mods/BurningTertium/roof_positions.lua" })
    {
        var path = Path.Combine(mod, relative.Replace('/', Path.DirectorySeparatorChar));
        yield return new("mod-" + Path.GetFileName(relative).Replace('.', '-'), "mods/BurningTertium/" + relative,
            null, 0, null, path, new FileInfo(path).Length, Safety.Hash(path), true, null);
    }
}

internal sealed record SourceSpec(string Id, string Target, string? BaseSource, long BaseSize, string? BaseHash,
    string OutputSource, long OutputSize, string OutputHash, bool Addition, string? BaseTarget);
