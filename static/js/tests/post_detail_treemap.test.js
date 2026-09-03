const assert = require("node:assert/strict");
const test = require("node:test");

const {
    getSquarifiedTreemap,
} = require("../post_detail.js");

const EPSILON = 1e-7;

const assertValidLayout = (items, width, height) => {
    const tiles = getSquarifiedTreemap(items, width, height);
    const total = items.reduce((sum, item) => sum + item.amount, 0);

    assert.equal(tiles.length, items.length);
    tiles.forEach((tile, index) => {
        [tile.x, tile.y, tile.width, tile.height].forEach((value) => {
            assert.ok(Number.isFinite(value));
            assert.ok(value >= 0);
        });
        assert.ok(tile.x + tile.width <= width + EPSILON);
        assert.ok(tile.y + tile.height <= height + EPSILON);

        const expectedArea = (items[index].amount / total) * width * height;
        const actualArea = tile.width * tile.height;
        assert.ok(Math.abs(actualArea - expectedArea) <= EPSILON * width * height);
    });

    for (let first = 0; first < tiles.length; first += 1) {
        for (let second = first + 1; second < tiles.length; second += 1) {
            const overlapWidth = Math.max(
                0,
                Math.min(tiles[first].x + tiles[first].width, tiles[second].x + tiles[second].width) -
                    Math.max(tiles[first].x, tiles[second].x),
            );
            const overlapHeight = Math.max(
                0,
                Math.min(tiles[first].y + tiles[first].height, tiles[second].y + tiles[second].height) -
                    Math.max(tiles[first].y, tiles[second].y),
            );
            assert.ok(overlapWidth * overlapHeight <= EPSILON);
        }
    }

    return tiles;
};

test("preserves proportional areas without overlap", () => {
    assertValidLayout(
        [
            { symbol: "AAA", amount: 40 },
            { symbol: "BBB", amount: 30 },
            { symbol: "CCC", amount: 20 },
            { symbol: "DDD", amount: 10 },
        ],
        800,
        400,
    );
    assertValidLayout(
        [
            { symbol: "AAA", amount: 1 },
            { symbol: "BBB", amount: 1 },
            { symbol: "CCC", amount: 1 },
            { symbol: "DDD", amount: 1 },
        ],
        640,
        360,
    );
});

test("consumes the short side in wide and tall containers", () => {
    const items = [
        { symbol: "AAA", amount: 6 },
        { symbol: "BBB", amount: 4 },
        { symbol: "CCC", amount: 3 },
        { symbol: "DDD", amount: 2 },
        { symbol: "EEE", amount: 1 },
    ];

    const wideTiles = assertValidLayout(items, 800, 400);
    assert.ok(wideTiles[0].width < 800);
    assert.equal(wideTiles[0].height, 400);

    const tallTiles = assertValidLayout(items, 400, 800);
    assert.equal(tallTiles[0].width, 400);
    assert.ok(tallTiles[0].height < 800);
});

test("produces finite non-negative geometry for one item and a tiny weight", () => {
    const singleTile = assertValidLayout([{ symbol: "AAA", amount: 1 }], 375, 240)[0];
    assert.deepEqual(
        { x: singleTile.x, y: singleTile.y, width: singleTile.width, height: singleTile.height },
        { x: 0, y: 0, width: 375, height: 240 },
    );

    assertValidLayout(
        [
            { symbol: "AAA", amount: 1 },
            { symbol: "TINY", amount: Number.EPSILON },
        ],
        997,
        313,
    );
});