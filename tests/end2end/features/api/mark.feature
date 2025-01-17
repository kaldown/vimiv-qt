Feature: Mark and tag images.

    Scenario: Mark current path
        Given I open 2 images
        When I run mark %
        Then there should be 1 marked images
        And image_01.jpg should be marked

    Scenario: Mark multiple paths
        Given I open 5 images
        When I run mark image_01.jpg image_02.jpg
        Then there should be 2 marked images
        And image_01.jpg should be marked
        And image_02.jpg should be marked

    Scenario: Load all marked images
        Given I open 5 images
        When I run mark image_01.jpg image_02.jpg
        And I run open %m
        Then the filelist should contain 2 images

    Scenario: Write a tag file
        Given I open 5 images
        When I run mark image_01.jpg image_02.jpg
        And I run tag-write test
        Then the tag file test should exist with 2 paths

    Scenario: Append to a tag file
        Given I open 5 images
        When I run mark image_01.jpg image_02.jpg
        And I run tag-write test
        And I run mark image_03.jpg
        And I run tag-write test
        Then the tag file test should exist with 3 paths

    Scenario: Load a tag file
        Given I open 5 images
        When I run mark image_01.jpg image_02.jpg
        And I run tag-write test
        And I run tag-load test
        Then there should be 2 marked images

    Scenario: Delete a tag file
        Given I open 5 images
        When I run mark image_01.jpg image_02.jpg
        And I run tag-write test
        And I run tag-delete test
        Then the tag file test should not exist
