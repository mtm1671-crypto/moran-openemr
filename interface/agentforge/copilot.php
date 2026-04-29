<?php

/**
 * AgentForge Clinical Co-Pilot OpenEMR launch bridge.
 *
 * @package   OpenEMR
 * @link      https://www.open-emr.org
 * @license   https://github.com/openemr/openemr/blob/master/LICENSE GNU General Public License 3
 */

require_once("../globals.php");

use OpenEMR\Common\Acl\AccessDeniedHelper;
use OpenEMR\Common\Acl\AclMain;
use OpenEMR\Common\Session\SessionWrapperFactory;
use OpenEMR\Common\Uuid\UuidRegistry;
use OpenEMR\Core\Header;
use OpenEMR\Core\OEGlobalsBag;
use OpenEMR\Services\AppointmentService;
use OpenEMR\Services\Globals\GlobalConnectorsEnum;
use OpenEMR\Services\PatientService;

if (!AclMain::aclCheckCore('patients', 'demo')) {
    AccessDeniedHelper::denyWithTemplate("ACL check failed for patients/demo: Clinical Co-Pilot", xl("Clinical Co-Pilot"));
}

$session = SessionWrapperFactory::getInstance()->getActiveSession();
$context = $_GET['context'] ?? 'global';
$pid = normalizePositiveInt($_GET['pid'] ?? null);
$appointmentEid = normalizePositiveInt($_GET['appointment_eid'] ?? null);

$launchParams = [
    'launch_context' => is_string($context) && $context !== '' ? $context : 'global',
    'openemr_site' => (string) $session->get('site_id'),
];

if ($appointmentEid !== null) {
    if (!AclMain::aclCheckCore('patients', 'appt')) {
        AccessDeniedHelper::denyWithTemplate("ACL check failed for patients/appt: Clinical Co-Pilot schedule launch", xl("Clinical Co-Pilot"));
    }

    $appointmentService = new AppointmentService();
    $appointments = $appointmentService->getAppointment($appointmentEid);
    $appointment = $appointments[0] ?? null;
    if (empty($appointment)) {
        AccessDeniedHelper::denyWithTemplate("Appointment not found for Clinical Co-Pilot launch", xl("Clinical Co-Pilot"));
    }

    $appointmentPid = normalizePositiveInt($appointment['pid'] ?? $appointment['pc_pid'] ?? null);
    if ($pid !== null && $appointmentPid !== null && $pid !== $appointmentPid) {
        AccessDeniedHelper::denyWithTemplate("Appointment patient mismatch for Clinical Co-Pilot launch", xl("Clinical Co-Pilot"));
    }

    $pid = $appointmentPid ?? $pid;
    $launchParams['launch_context'] = 'schedule';
    $launchParams['appointment_eid'] = (string) $appointmentEid;
    if (!empty($appointment['pc_uuid']) && is_string($appointment['pc_uuid'])) {
        $launchParams['appointment_id'] = $appointment['pc_uuid'];
    }
}

if ($pid !== null) {
    $patientContext = getPatientLaunchContext($pid);
    $launchParams = array_merge($launchParams, $patientContext);
}

$launchUrl = buildCopilotLaunchUrl($launchParams);

?>
<!doctype html>
<html>
<head>
    <title><?php echo xlt('Clinical Co-Pilot'); ?></title>
    <?php Header::setupHeader(); ?>
</head>
<body class="body_top">
<main class="container mt-4">
    <div class="card">
        <div class="card-body">
            <h1 class="h4"><?php echo xlt('Clinical Co-Pilot'); ?></h1>
            <p><?php echo xlt('Opening the patient-scoped Co-Pilot workspace.'); ?></p>
            <p>
                <a id="agentforge-copilot-launch" class="btn btn-primary" href="<?php echo attr($launchUrl); ?>">
                    <?php echo xlt('Open Co-Pilot'); ?>
                </a>
                <a class="btn btn-secondary" href="<?php echo attr($launchUrl); ?>" target="_blank" rel="noopener">
                    <?php echo xlt('Open in New Window'); ?>
                </a>
            </p>
        </div>
    </div>
</main>
<script>
    window.addEventListener('DOMContentLoaded', function () {
        top.restoreSession();
        window.location.replace(<?php echo js_escape($launchUrl); ?>);
    });
</script>
</body>
</html>
<?php

function normalizePositiveInt(mixed $value): ?int
{
    if ($value === null || $value === '') {
        return null;
    }
    if (!is_scalar($value) || filter_var($value, FILTER_VALIDATE_INT) === false) {
        return null;
    }
    $number = (int) $value;
    return $number > 0 ? $number : null;
}

/**
 * @return array<string,string>
 */
function getPatientLaunchContext(int $pid): array
{
    $patient = sqlQuery("SELECT pid, squad FROM patient_data WHERE pid = ?", [$pid]);
    if (empty($patient)) {
        AccessDeniedHelper::denyWithTemplate("Patient not found for Clinical Co-Pilot launch", xl("Clinical Co-Pilot"));
    }

    if (!empty($patient['squad']) && !AclMain::aclCheckCore('squads', $patient['squad'])) {
        AccessDeniedHelper::denyWithTemplate("ACL check failed for patient squad: Clinical Co-Pilot", xl("Clinical Co-Pilot"));
    }

    UuidRegistry::createMissingUuidsForTables(['patient_data']);
    $patientService = new PatientService();
    $patientUuid = UuidRegistry::uuidToString($patientService->getUuid($pid));

    return [
        'patient_id' => $patientUuid,
        'openemr_pid' => (string) $pid,
    ];
}

/**
 * @param array<string,string> $params
 */
function buildCopilotLaunchUrl(array $params): string
{
    $baseUrl = trim((string) (getenv('AGENTFORGE_COPILOT_URL') ?: ''));
    $globalKey = GlobalConnectorsEnum::AGENTFORGE_COPILOT_URL->value;
    if ($baseUrl === '' && OEGlobalsBag::getInstance()->has($globalKey)) {
        $baseUrl = trim(OEGlobalsBag::getInstance()->getString($globalKey));
    }
    if ($baseUrl === '') {
        $baseUrl = 'http://127.0.0.1:3001';
    }

    $parts = parse_url($baseUrl);
    if (
        !is_array($parts)
        || empty($parts['scheme'])
        || !in_array($parts['scheme'], ['http', 'https'], true)
        || empty($parts['host'])
    ) {
        $baseUrl = 'http://127.0.0.1:3001';
    }

    $separator = str_contains($baseUrl, '?') ? '&' : '?';
    return $baseUrl . $separator . http_build_query($params);
}
