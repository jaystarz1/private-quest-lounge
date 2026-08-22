// Solves the MetaPerson arm chain after Hubs has positioned the tracked hand
// effectors. Stock ik-controller only drives Head, LeftHand, and RightHand,
// leaving the shoulder/elbow/forearm bones in their rest pose.
const { Vector3, Quaternion } = THREE;

const SIDES = [
  {
    hand: "LeftHand",
    upper: ["LeftShoulder", "LeftArm"],
    lower: ["LeftForeArm", "LeftForeArm1", "LeftForeArm2"],
    sign: 1,
    wristTwistSign: 1
  },
  {
    hand: "RightHand",
    upper: ["RightShoulder", "RightArm"],
    lower: ["RightForeArm", "RightForeArm1", "RightForeArm2"],
    sign: -1,
    wristTwistSign: 1,
    continuousWristRoll: true
  }
];

const q = new Quaternion();
const parentQ = new Quaternion();
const deltaQ = new Quaternion();
const handQ = new Quaternion();
const handDeltaQ = new Quaternion();
const twistQ = new Quaternion();
const weightedTwistQ = new Quaternion();
const shoulder = new Vector3();
const wrist = new Vector3();
const elbow = new Vector3();
const target = new Vector3();
const axis = new Vector3();
const outward = new Vector3();
const down = new Vector3();
const upperDir = new Vector3();
const lowerDir = new Vector3();

function snapshotBone(bone, fallbackTail) {
  bone.updateWorldMatrix(true, false);
  const head = new Vector3();
  const tail = new Vector3();
  bone.getWorldPosition(head);
  const child = bone.children.find(childBone => childBone.isBone);
  if (child) {
    child.updateWorldMatrix(true, false);
    child.getWorldPosition(tail);
  } else if (fallbackTail) {
    tail.copy(fallbackTail);
  } else {
    return null;
  }
  const direction = tail.sub(head).normalize();
  bone.getWorldQuaternion(q);
  return { bone, restDirection: direction, restQuaternion: q.clone() };
}

function aim(snapshot, worldDirection, wristRotation, wristRoll = 0, wristTwistSign = 1) {
  const { bone, restDirection, restQuaternion } = snapshot;
  deltaQ.setFromUnitVectors(restDirection, worldDirection);
  q.copy(deltaQ).multiply(restQuaternion);
  if (wristRotation && wristRoll > 0) {
    const amount =
      wristRotation.x * worldDirection.x + wristRotation.y * worldDirection.y + wristRotation.z * worldDirection.z;
    twistQ.set(worldDirection.x * amount, worldDirection.y * amount, worldDirection.z * amount, wristRotation.w);
    if (twistQ.lengthSq() > 0.000001) {
      if (wristTwistSign < 0) twistQ.invert();
      weightedTwistQ.identity().slerp(twistQ.normalize(), wristRoll);
      q.premultiply(weightedTwistQ);
    }
  }
  if (bone.parent) {
    bone.parent.getWorldQuaternion(parentQ);
    parentQ.invert();
    bone.quaternion.copy(parentQ.multiply(q));
  } else {
    bone.quaternion.copy(q);
  }
  bone.matrixNeedsUpdate = true;
}

function getSignedTwistAngle(rotation, worldDirection) {
  const amount = rotation.x * worldDirection.x + rotation.y * worldDirection.y + rotation.z * worldDirection.z;
  const angle = 2 * Math.atan2(amount, rotation.w);
  return Math.atan2(Math.sin(angle), Math.cos(angle));
}

function unwrapAngle(angle, previousAngle) {
  while (angle - previousAngle > Math.PI) angle -= Math.PI * 2;
  while (angle - previousAngle < -Math.PI) angle += Math.PI * 2;
  return angle;
}

function aimWithContinuousRoll(snapshot, worldDirection, wristAngle, wristRoll, wristTwistSign = 1) {
  const { bone, restDirection, restQuaternion } = snapshot;
  deltaQ.setFromUnitVectors(restDirection, worldDirection);
  q.copy(deltaQ).multiply(restQuaternion);
  if (wristRoll > 0) {
    weightedTwistQ.setFromAxisAngle(worldDirection, wristAngle * wristRoll * wristTwistSign);
    q.premultiply(weightedTwistQ);
  }
  if (bone.parent) {
    bone.parent.getWorldQuaternion(parentQ);
    parentQ.invert();
    bone.quaternion.copy(parentQ.multiply(q));
  } else {
    bone.quaternion.copy(q);
  }
  bone.matrixNeedsUpdate = true;
}

AFRAME.registerComponent("avatar-arm-ik", {
  init() {
    this.rigs = null;
  },

  setup() {
    const root = this.el.object3D;
    const rigs = [];
    for (const side of SIDES) {
      const hand = root.getObjectByName(side.hand);
      const upperBones = side.upper.map(name => root.getObjectByName(name));
      const lowerBones = side.lower.map(name => root.getObjectByName(name));
      if (!hand || upperBones.some(bone => !bone) || lowerBones.some(bone => !bone)) return false;
      hand.updateWorldMatrix(true, false);
      hand.getWorldPosition(wrist);
      hand.getWorldQuaternion(handQ);
      const upper = upperBones.map(bone => snapshotBone(bone));
      const lower = lowerBones.map(bone => snapshotBone(bone, wrist));
      if (upper.some(x => !x) || lower.some(x => !x)) return false;
      const elbowBone = lowerBones[0];
      upperBones[0].getWorldPosition(shoulder);
      elbowBone.getWorldPosition(elbow);
      const lowerLength = elbow.distanceTo(wrist);
      const lowerRollWeights = lowerBones.map((bone, index) => {
        if (index === 0) return 0;
        bone.getWorldPosition(target);
        return Math.min(1, Math.max(0, elbow.distanceTo(target) / lowerLength));
      });
      rigs.push({
        side,
        hand,
        handRestInverseQuaternion: handQ.clone().invert(),
        upper,
        lower,
        lowerRollWeights,
        wristTwistAngle: 0,
        hasWristTwistAngle: false,
        upperLength: shoulder.distanceTo(elbow),
        lowerLength
      });
    }
    this.rigs = rigs;
    return true;
  },

  tock() {
    if (!this.rigs && !this.setup()) return;
    for (const rig of this.rigs) {
      const shoulderBone = rig.upper[0].bone;
      shoulderBone.getWorldPosition(shoulder);
      rig.hand.getWorldPosition(wrist);
      target.subVectors(wrist, shoulder);
      const distance = target.length();
      if (distance < 0.001) continue;
      axis.copy(target).multiplyScalar(1 / distance);
      shoulderBone.parent.getWorldQuaternion(q);
      outward.set(rig.side.sign, 0, 0).applyQuaternion(q);
      down.set(0, -1, 0).applyQuaternion(q);
      outward.addScaledVector(axis, -outward.dot(axis)).normalize();
      down.addScaledVector(axis, -down.dot(axis)).normalize();
      outward.addScaledVector(down, 0.55).normalize();
      const a = rig.upperLength;
      const b = rig.lowerLength;
      const d = Math.min(Math.max(distance, Math.abs(a - b) + 0.001), a + b - 0.001);
      const along = (a * a - b * b + d * d) / (2 * d);
      const height = Math.sqrt(Math.max(0, a * a - along * along));
      elbow.copy(shoulder).addScaledVector(axis, along).addScaledVector(outward, height);
      upperDir.subVectors(elbow, shoulder).normalize();
      lowerDir.subVectors(wrist, elbow).normalize();

      rig.hand.getWorldQuaternion(handQ);
      const wristRotation = handDeltaQ.copy(handQ).multiply(rig.handRestInverseQuaternion);
      let wristTwistAngle = 0;
      if (rig.side.continuousWristRoll) {
        wristTwistAngle = getSignedTwistAngle(wristRotation, lowerDir);
        if (rig.hasWristTwistAngle) {
          wristTwistAngle = unwrapAngle(wristTwistAngle, rig.wristTwistAngle);
        } else {
          rig.hasWristTwistAngle = true;
        }
        rig.wristTwistAngle = wristTwistAngle;
      }

      for (const bone of rig.upper) aim(bone, upperDir);
      shoulderBone.updateWorldMatrix(true, true);
      for (let i = 0; i < rig.lower.length; i++) {
        // These are localized twist helpers at different points along the
        // forearm. Give each one only the roll reached at its bind position so
        // the rotation builds toward the wrist instead of pinching below the
        // elbow when the hand passes through a vertical orientation.
        const wristRoll = rig.lowerRollWeights[i];
        if (rig.side.continuousWristRoll) {
          aimWithContinuousRoll(rig.lower[i], lowerDir, wristTwistAngle, wristRoll, rig.side.wristTwistSign);
        } else {
          aim(rig.lower[i], lowerDir, wristRotation, wristRoll, rig.side.wristTwistSign);
        }
      }
    }
  }
});
