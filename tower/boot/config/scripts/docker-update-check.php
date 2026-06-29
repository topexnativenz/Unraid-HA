#!/usr/bin/php -q
<?php
/**
 * List Unraid Docker containers with updates available.
 * Uses dynamix.docker.manager update-status (same as WebUI "Check for Updates").
 *
 * Output (stdout): one line per pending update:
 *   CONTAINER_NAME|TEMPLATE_BASENAME|IMAGE_REPO
 */
$docroot = '/usr/local/emhttp';
require_once "$docroot/webGui/include/Helpers.php";
require_once "$docroot/plugins/dynamix.docker.manager/include/DockerClient.php";

$DockerUpdate    = new DockerUpdate();
$DockerTemplates = new DockerTemplates();

$DockerUpdate->reloadUpdateStatus();

global $dockerManPaths;
$statusFile = $dockerManPaths['update-status'] ?? '/var/lib/docker/unraid-update-status.json';
$updateStatus = is_file($statusFile)
    ? (json_decode(file_get_contents($statusFile), true) ?: [])
    : [];

$templatesDir = '/boot/config/plugins/dockerMan/templates-user';
if (!is_dir($templatesDir)) {
    fwrite(STDERR, "templates-user not found: $templatesDir\n");
    exit(1);
}

foreach (glob("$templatesDir/*.xml") ?: [] as $tmplFile) {
    $xml = @simplexml_load_file($tmplFile);
    if (!$xml || empty($xml->Name) || empty($xml->Repository)) {
        continue;
    }

    $name = trim((string) $xml->Name);
    $repo = DockerUtil::ensureImageTag(trim((string) $xml->Repository));

    if (!isset($updateStatus[$repo])) {
        continue;
    }
    $entry = $updateStatus[$repo];
    if (!is_array($entry) || ($entry['status'] ?? '') !== 'false') {
        continue;
    }

    $templateBase = basename($tmplFile, '.xml');
    echo "$name|$templateBase|$repo\n";
}
